"""
YancoHub — Native Gamepad Bridge
Reads gamepad input via multiple backends and pushes state to the pywebview
frontend via evaluate_js().

WebView2 does NOT support the W3C Gamepad API — navigator.getGamepads()
returns null. This module bridges the gap by polling controllers natively
and injecting state into JavaScript, where a polyfill (gamepad-bridge.js)
makes it available through the standard Gamepad API surface.

Detection priority:
  1. HID (hidapi) — DualSense, DualSense Edge, DualShock 4 via USB or Bluetooth
  2. XInput (xinput1_4.dll) — Xbox controllers, DualSense via Steam Input
  3. WinMM (winmm.dll) — generic DirectInput controllers (legacy fallback)
"""

import ctypes
import ctypes.wintypes as wt
import json
import logging
import threading
import time

logger = logging.getLogger('yancohub.gamepad')

# W3C Standard Gamepad: 17 buttons, 4 axes
STD_BUTTONS = 17
STD_AXES = 4


def _btn(pressed: bool) -> dict:
    return {'pressed': pressed, 'value': 1.0 if pressed else 0.0}


# ── HID (hidapi) — DualSense, DualSense Edge, DualShock 4 ────────────────

try:
    import hid as _hid_lib
    _hid_available = True
except ImportError:
    _hid_lib = None
    _hid_available = False

# Known Sony controllers: (VID, PID) → (human name, parser type)
_KNOWN_HID = {
    (0x054C, 0x0CE6): ('DualSense Wireless Controller', 'dualsense'),
    (0x054C, 0x0DF2): ('DualSense Edge Wireless Controller', 'dualsense'),
    (0x054C, 0x05C4): ('DualShock 4 (v1)', 'ds4'),
    (0x054C, 0x09CC): ('DualShock 4 (v2)', 'ds4'),
}

# D-pad hat → (up, down, left, right)
_HID_DPAD = {
    0: (True, False, False, False),   # N
    1: (True, False, False, True),    # NE
    2: (False, False, False, True),   # E
    3: (False, True, False, True),    # SE
    4: (False, True, False, False),   # S
    5: (False, True, True, False),    # SW
    6: (False, False, True, False),   # W
    7: (True, False, True, False),    # NW
}


def _hid_buttons_to_w3c(btn0: int, btn1: int, btn2: int,
                         l2_analog: int, r2_analog: int) -> list[dict]:
    """Convert HID button bytes to W3C standard button array."""
    buttons = [_btn(False) for _ in range(STD_BUTTONS)]

    # Face buttons from btn0 (bits 4-7)
    buttons[0] = _btn(bool(btn0 & 0x20))   # Cross → A
    buttons[1] = _btn(bool(btn0 & 0x40))   # Circle → B
    buttons[2] = _btn(bool(btn0 & 0x10))   # Square → X
    buttons[3] = _btn(bool(btn0 & 0x80))   # Triangle → Y

    # Shoulders from btn1
    buttons[4] = _btn(bool(btn1 & 0x01))   # L1 → LB
    buttons[5] = _btn(bool(btn1 & 0x02))   # R1 → RB

    # Analog triggers → buttons 6, 7
    lt = round(l2_analog / 255.0, 4)
    rt = round(r2_analog / 255.0, 4)
    buttons[6] = {'pressed': lt > 0.12, 'value': lt}
    buttons[7] = {'pressed': rt > 0.12, 'value': rt}

    # Meta buttons from btn1
    buttons[8] = _btn(bool(btn1 & 0x10))   # Create/Share → Select
    buttons[9] = _btn(bool(btn1 & 0x20))   # Options → Start
    buttons[10] = _btn(bool(btn1 & 0x40))  # L3 → LS
    buttons[11] = _btn(bool(btn1 & 0x80))  # R3 → RS

    # D-pad from btn0 lower nibble
    dpad = btn0 & 0x0F
    up, down, left, right = _HID_DPAD.get(dpad, (False, False, False, False))
    buttons[12] = _btn(up)
    buttons[13] = _btn(down)
    buttons[14] = _btn(left)
    buttons[15] = _btn(right)

    # Home from btn2
    buttons[16] = _btn(bool(btn2 & 0x01))  # PS → Home

    return buttons


def _hid_sticks_to_axes(lx: int, ly: int, rx: int, ry: int) -> list[float]:
    """Convert HID stick bytes [0-255] to W3C axes [-1.0, 1.0]."""
    def norm(v: int) -> float:
        return round(max(-1.0, min(1.0, (v - 128) / 127.0)), 4)
    return [norm(lx), norm(ly), norm(rx), norm(ry)]


class _HIDReader:
    """Persistent HID connection to a supported gamepad."""

    def __init__(self):
        self._dev = None
        self._name: str = ''
        self._type: str = ''          # 'dualsense' or 'ds4'
        self._vid: int = 0
        self._pid: int = 0
        self._last: dict | None = None
        self._retry_at: float = 0.0

    @property
    def connected(self) -> bool:
        return self._dev is not None

    @property
    def controller_name(self) -> str:
        return self._name

    def read(self) -> dict | None:
        """Read current state. Returns W3C gamepad dict or None."""
        if not _hid_available:
            return None

        just_connected = False
        if not self._dev:
            now = time.monotonic()
            if now < self._retry_at:
                return None
            self._try_connect()
            if not self._dev:
                self._retry_at = time.monotonic() + 2.0
                return None
            just_connected = True

        try:
            if just_connected:
                # First read after connect: brief blocking read to get initial
                # state, otherwise non-blocking returns empty and we fall
                # through to a lower-priority backend.
                self._dev.set_nonblocking(False)
                data = self._dev.read(78, timeout_ms=50)
                self._dev.set_nonblocking(True)
            else:
                data = self._dev.read(78)  # non-blocking
            if data:
                parsed = self._parse(bytes(data))
                if parsed:
                    self._last = parsed
            return self._last
        except Exception:
            self._close()
            return None

    def _try_connect(self):
        """Scan HID devices for a known controller and open it."""
        try:
            for info in _hid_lib.enumerate():
                key = (info['vendor_id'], info['product_id'])
                if key not in _KNOWN_HID:
                    continue
                # Usage page 1 (Generic Desktop), usage 5 (Gamepad)
                if info.get('usage_page') != 1 or info.get('usage') != 5:
                    continue

                name, ctype = _KNOWN_HID[key]
                try:
                    dev = _hid_lib.device()
                    dev.open_path(info['path'])
                    dev.set_nonblocking(True)
                    self._dev = dev
                    self._name = name
                    self._type = ctype
                    self._vid = info['vendor_id']
                    self._pid = info['product_id']
                    logger.info("HID gamepad connected: %s (VID=%04X PID=%04X)",
                                name, self._vid, self._pid)
                    return
                except Exception as e:
                    logger.debug("HID open failed for %s: %s", name, e)
        except Exception as e:
            logger.debug("HID enumerate error: %s", e)

    def _close(self):
        if self._dev:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None
            self._last = None
            logger.info("HID gamepad disconnected: %s", self._name)

    def _parse(self, data: bytes) -> dict | None:
        """Route to the correct parser based on controller type."""
        if self._type == 'dualsense':
            return self._parse_dualsense(data)
        elif self._type == 'ds4':
            return self._parse_ds4(data)
        return None

    def _parse_dualsense(self, data: bytes) -> dict | None:
        """Parse DualSense input report to W3C format.

        DualSense report layouts:
          USB  (0x01, 64B): offset 1 — LX LY RX RY L2 R2 [counter] btn0 btn1 btn2
          BT full (0x31, 78B): offset 2 — same as USB
          BT simple (0x01, ~10B): offset 1 — same as USB (truncated)
        """
        rid = data[0]
        if rid == 0x31 and len(data) >= 12:
            off = 2   # BT full report: skip report ID + BT header
        elif rid == 0x01 and len(data) >= 11:
            off = 1   # USB or BT simple: skip report ID
        else:
            return None

        lx, ly = data[off], data[off + 1]
        rx, ry = data[off + 2], data[off + 3]
        l2, r2 = data[off + 4], data[off + 5]
        # off + 6 = sequence counter (skip)
        btn0 = data[off + 7]
        btn1 = data[off + 8]
        btn2 = data[off + 9]

        return {
            'id': f'{self._name} (STANDARD GAMEPAD HID)',
            'index': 0,
            'mapping': 'standard',
            'buttons': _hid_buttons_to_w3c(btn0, btn1, btn2, l2, r2),
            'axes': _hid_sticks_to_axes(lx, ly, rx, ry),
        }

    def _parse_ds4(self, data: bytes) -> dict | None:
        """Parse DualShock 4 input report to W3C format.

        DS4 report layouts:
          USB  (0x01, 64B): offset 1 — LX LY RX RY btn0 btn1 btn2 L2 R2
          BT   (0x11, 78B): offset 3 — same as USB
        """
        rid = data[0]
        if rid == 0x11 and len(data) >= 12:
            off = 3   # BT: skip report ID + 2 BT header bytes
        elif rid == 0x01 and len(data) >= 10:
            off = 1   # USB: skip report ID
        else:
            return None

        lx, ly = data[off], data[off + 1]
        rx, ry = data[off + 2], data[off + 3]
        btn0 = data[off + 4]
        btn1 = data[off + 5]
        btn2 = data[off + 6]
        l2 = data[off + 7]
        r2 = data[off + 8]

        return {
            'id': f'{self._name} (STANDARD GAMEPAD HID)',
            'index': 0,
            'mapping': 'standard',
            'buttons': _hid_buttons_to_w3c(btn0, btn1, btn2, l2, r2),
            'axes': _hid_sticks_to_axes(lx, ly, rx, ry),
        }

    def diagnostics(self) -> dict:
        """Return HID detection info."""
        result: dict = {
            'available': _hid_available,
            'connected': self.connected,
            'controller': self._name if self.connected else None,
            'devices': [],
        }
        if _hid_available:
            try:
                for info in _hid_lib.enumerate():
                    key = (info['vendor_id'], info['product_id'])
                    if key in _KNOWN_HID:
                        result['devices'].append({
                            'name': _KNOWN_HID[key][0],
                            'vid': f'{info["vendor_id"]:04X}',
                            'pid': f'{info["product_id"]:04X}',
                            'usage_page': info.get('usage_page'),
                            'usage': info.get('usage'),
                            'product': info.get('product_string', ''),
                        })
            except Exception:
                pass
        return result


# Module-level HID reader instance (persistent connection)
_hid_reader = _HIDReader()


# ── XInput (xinput1_4.dll) ─────────────────────────────────────────────────

class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ('wButtons', wt.WORD),
        ('bLeftTrigger', ctypes.c_ubyte),
        ('bRightTrigger', ctypes.c_ubyte),
        ('sThumbLX', ctypes.c_short),
        ('sThumbLY', ctypes.c_short),
        ('sThumbRX', ctypes.c_short),
        ('sThumbRY', ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ('dwPacketNumber', wt.DWORD),
        ('Gamepad', XINPUT_GAMEPAD),
    ]


# XInput button bitmask → W3C Standard button index
_XI_BTN_MAP = [
    (0x1000, 0),   # A → Button 0
    (0x2000, 1),   # B → Button 1
    (0x4000, 2),   # X → Button 2
    (0x8000, 3),   # Y → Button 3
    (0x0100, 4),   # LB → Button 4
    (0x0200, 5),   # RB → Button 5
    # Triggers are analog → buttons 6, 7 (handled separately)
    (0x0020, 8),   # Back → Button 8
    (0x0010, 9),   # Start → Button 9
    (0x0040, 10),  # LS → Button 10
    (0x0080, 11),  # RS → Button 11
    (0x0001, 12),  # D-Up → Button 12
    (0x0002, 13),  # D-Down → Button 13
    (0x0004, 14),  # D-Left → Button 14
    (0x0008, 15),  # D-Right → Button 15
]

_xinput = None
for _dll_name in ('xinput1_4', 'xinput1_3', 'xinput9_1_0'):
    try:
        _xinput = ctypes.WinDLL(_dll_name)
        break
    except OSError:
        continue


def _read_xinput(index: int) -> dict | None:
    """Read XInput gamepad at slot *index*. Returns W3C-mapped state or None."""
    if not _xinput:
        return None
    state = XINPUT_STATE()
    if _xinput.XInputGetState(index, ctypes.byref(state)) != 0:
        return None

    gp = state.Gamepad
    buttons = [_btn(False) for _ in range(STD_BUTTONS)]

    for mask, idx in _XI_BTN_MAP:
        buttons[idx] = _btn(bool(gp.wButtons & mask))

    lt = round(gp.bLeftTrigger / 255.0, 4)
    rt = round(gp.bRightTrigger / 255.0, 4)
    buttons[6] = {'pressed': lt > 0.12, 'value': lt}
    buttons[7] = {'pressed': rt > 0.12, 'value': rt}

    axes = [
        round(max(-1.0, gp.sThumbLX / 32767.0), 4),
        round(max(-1.0, -gp.sThumbLY / 32767.0), 4),
        round(max(-1.0, gp.sThumbRX / 32767.0), 4),
        round(max(-1.0, -gp.sThumbRY / 32767.0), 4),
    ]

    return {
        'id': f'Xbox Controller (STANDARD GAMEPAD XInput #{index})',
        'index': 0,
        'mapping': 'standard',
        'buttons': buttons,
        'axes': axes,
    }


# ── WinMM Joystick API (winmm.dll) — legacy fallback ─────────────────────

MAXPNAMELEN = 32


class JOYCAPSW(ctypes.Structure):
    _fields_ = [
        ('wMid', wt.WORD), ('wPid', wt.WORD),
        ('szPname', ctypes.c_wchar * MAXPNAMELEN),
        ('wXmin', wt.UINT), ('wXmax', wt.UINT),
        ('wYmin', wt.UINT), ('wYmax', wt.UINT),
        ('wZmin', wt.UINT), ('wZmax', wt.UINT),
        ('wNumButtons', wt.UINT),
        ('wPeriodMin', wt.UINT), ('wPeriodMax', wt.UINT),
        ('wRmin', wt.UINT), ('wRmax', wt.UINT),
        ('wUmin', wt.UINT), ('wUmax', wt.UINT),
        ('wVmin', wt.UINT), ('wVmax', wt.UINT),
        ('wCaps', wt.UINT), ('wMaxAxes', wt.UINT),
        ('wNumAxes', wt.UINT), ('wMaxButtons', wt.UINT),
        ('szRegKey', ctypes.c_wchar * MAXPNAMELEN),
        ('szOEMVxD', ctypes.c_wchar * 260),
    ]


class JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ('dwSize', wt.DWORD), ('dwFlags', wt.DWORD),
        ('dwXpos', wt.DWORD), ('dwYpos', wt.DWORD),
        ('dwZpos', wt.DWORD), ('dwRpos', wt.DWORD),
        ('dwUpos', wt.DWORD), ('dwVpos', wt.DWORD),
        ('dwButtons', wt.DWORD), ('dwButtonNumber', wt.DWORD),
        ('dwPOV', wt.DWORD),
        ('dwReserved1', wt.DWORD), ('dwReserved2', wt.DWORD),
    ]


try:
    _winmm = ctypes.WinDLL('winmm')
except OSError:
    _winmm = None


def _norm_axis(value: int, lo: int, hi: int) -> float:
    """Normalize unsigned axis [lo, hi] → [-1.0, 1.0]."""
    if hi <= lo:
        return 0.0
    return round((2.0 * (value - lo) / (hi - lo)) - 1.0, 4)


def _pov_to_dpad(pov: int) -> tuple[bool, bool, bool, bool]:
    """POV angle (hundredths of degrees, or 0xFFFF=centered) → (up, down, left, right)."""
    if pov == 0xFFFF or pov > 36000:
        return (False, False, False, False)
    deg = pov / 100.0
    up    = deg >= 315 or deg <= 45
    right = 45 <= deg <= 135
    down  = 135 <= deg <= 225
    left  = 225 <= deg <= 315
    return (up, down, left, right)


def _is_playstation(name: str, num_buttons: int) -> bool:
    """Detect PlayStation controllers (DualSense, DualShock 4)."""
    lower = name.lower()
    return ('wireless controller' in lower or 'dualsense' in lower
            or 'dualshock' in lower or num_buttons >= 13)


# DualSense / DualShock 4 DirectInput button → W3C Standard button
_DS_BTN = {
    1: 0, 2: 1, 0: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7,
    8: 8, 9: 9, 10: 10, 11: 11, 12: 16,
}

# Generic / Xbox DirectInput button → W3C Standard button
_GENERIC_BTN = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 8, 7: 9, 8: 10, 9: 11,
}


def _read_winmm(joy_id: int) -> dict | None:
    """Read WinMM joystick at *joy_id*. Returns W3C-mapped state or None."""
    if not _winmm:
        return None

    info = JOYINFOEX()
    info.dwSize = ctypes.sizeof(JOYINFOEX)
    info.dwFlags = 0xFF | 0x200

    if _winmm.joyGetPosEx(joy_id, ctypes.byref(info)) != 0:
        return None

    caps = JOYCAPSW()
    if _winmm.joyGetDevCapsW(joy_id, ctypes.byref(caps), ctypes.sizeof(JOYCAPSW)) != 0:
        return None

    name = caps.szPname.strip()
    n_btn = caps.wNumButtons
    n_ax = caps.wNumAxes
    is_ps = _is_playstation(name, n_btn)
    btn_map = _DS_BTN if is_ps else _GENERIC_BTN

    buttons = [_btn(False) for _ in range(STD_BUTTONS)]
    for di_idx in range(min(n_btn, 32)):
        pressed = bool(info.dwButtons & (1 << di_idx))
        if di_idx in btn_map:
            buttons[btn_map[di_idx]] = _btn(pressed)

    left_x = _norm_axis(info.dwXpos, caps.wXmin, caps.wXmax)
    left_y = _norm_axis(info.dwYpos, caps.wYmin, caps.wYmax)

    if is_ps and n_ax >= 6:
        right_x = _norm_axis(info.dwZpos, caps.wZmin, caps.wZmax)
        right_y = _norm_axis(info.dwVpos, caps.wVmin, caps.wVmax)
        l2 = round(max(0.0, _norm_axis(info.dwRpos, caps.wRmin, caps.wRmax)), 4)
        r2 = round(max(0.0, _norm_axis(info.dwUpos, caps.wUmin, caps.wUmax)), 4)
        buttons[6] = {'pressed': l2 > 0.12, 'value': l2}
        buttons[7] = {'pressed': r2 > 0.12, 'value': r2}
    elif is_ps and n_ax >= 4:
        right_x = _norm_axis(info.dwZpos, caps.wZmin, caps.wZmax)
        right_y = _norm_axis(info.dwRpos, caps.wRmin, caps.wRmax)
    else:
        right_x = _norm_axis(info.dwZpos, caps.wZmin, caps.wZmax) if n_ax >= 3 else 0.0
        right_y = _norm_axis(info.dwRpos, caps.wRmin, caps.wRmax) if n_ax >= 4 else 0.0

    axes = [left_x, left_y, right_x, right_y]

    up, down, left, right = _pov_to_dpad(info.dwPOV)
    buttons[12] = _btn(up)
    buttons[13] = _btn(down)
    buttons[14] = _btn(left)
    buttons[15] = _btn(right)

    return {
        'id': f'{name} (STANDARD GAMEPAD)',
        'index': 0,
        'mapping': 'standard',
        'buttons': buttons,
        'axes': axes,
    }


# ── Public API ─────────────────────────────────────────────────────────────

def read_gamepad() -> dict | None:
    """Read the first connected gamepad.  Returns W3C-mapped state or None.

    Priority: HID (DualSense/DS4) → XInput (Xbox) → WinMM (legacy fallback).
    """
    # 1. HID — reliable for DualSense/DS4 via USB and Bluetooth
    state = _hid_reader.read()
    if state:
        return state

    # 2. XInput — Xbox controllers and Steam Input
    for i in range(4):
        state = _read_xinput(i)
        if state:
            return state

    # 3. WinMM — legacy fallback for everything else
    if _winmm:
        num_devs = _winmm.joyGetNumDevs()
        for i in range(min(num_devs, 16)):
            state = _read_winmm(i)
            if state:
                return state

    return None


def gamepad_diagnostics() -> dict:
    """Return diagnostic info about all gamepad detection backends."""
    result: dict = {
        'hid': _hid_reader.diagnostics(),
        'xinput_available': _xinput is not None,
        'winmm_available': _winmm is not None,
        'xinput_devices': [],
        'winmm_devices': [],
        'detected': False,
        'controller': None,
    }

    if _xinput:
        for i in range(4):
            st = XINPUT_STATE()
            if _xinput.XInputGetState(i, ctypes.byref(st)) == 0:
                result['xinput_devices'].append(f'XInput #{i}')

    if _winmm:
        num_devs = _winmm.joyGetNumDevs()
        for i in range(min(num_devs, 16)):
            caps = JOYCAPSW()
            if _winmm.joyGetDevCapsW(i, ctypes.byref(caps),
                                      ctypes.sizeof(JOYCAPSW)) == 0:
                info = JOYINFOEX()
                info.dwSize = ctypes.sizeof(JOYINFOEX)
                info.dwFlags = 0xFF | 0x200
                if _winmm.joyGetPosEx(i, ctypes.byref(info)) == 0:
                    result['winmm_devices'].append({
                        'id': i,
                        'name': caps.szPname.strip(),
                        'buttons': caps.wNumButtons,
                        'axes': caps.wNumAxes,
                    })

    state = read_gamepad()
    if state:
        result['detected'] = True
        result['controller'] = state['id']

    return result


class GamepadBridge:
    """Background thread that polls the native gamepad and pushes state
    into the pywebview window via evaluate_js()."""

    _RECONNECT_INTERVAL = 3.0

    def __init__(self, window):
        self._window = window
        self._running = False
        self._thread = None
        self._was_connected = False
        self._last_json = None
        self._last_connect_push = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='gamepad-bridge')
        self._thread.start()
        logger.info("Gamepad bridge started")

    def stop(self):
        self._running = False

    # ── internals ──

    def _push(self, js: str) -> bool:
        """Safely evaluate JS in the window. Returns True if successful."""
        try:
            self._window.evaluate_js(js)
            return True
        except Exception:
            return False

    def _wait_for_js(self, timeout: float = 30.0) -> bool:
        """Poll until the JS bridge polyfill signals readiness."""
        deadline = time.monotonic() + timeout
        while self._running and time.monotonic() < deadline:
            try:
                result = self._window.evaluate_js(
                    'window._gpBridgeReady === true')
                if result:
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def _loop(self):
        if self._wait_for_js():
            logger.info("Gamepad bridge: JS polyfill ready")
        else:
            logger.warning("Gamepad bridge: JS polyfill not ready after timeout, "
                           "starting anyway")

        diag = gamepad_diagnostics()
        if diag['detected']:
            logger.info("Gamepad detected at startup: %s", diag['controller'])
        else:
            backends = []
            if diag['hid']['available']:
                backends.append(f"HID({len(diag['hid']['devices'])} devices)")
            backends.append(f"XInput={'yes' if diag['xinput_available'] else 'no'}")
            backends.append(f"WinMM={'yes' if diag['winmm_available'] else 'no'}")
            logger.info("No gamepad detected at startup [%s]", ', '.join(backends))

        while self._running:
            try:
                state = read_gamepad()
                now = time.monotonic()

                if state is not None:
                    sj = json.dumps(state, separators=(',', ':'))

                    if not self._was_connected:
                        self._was_connected = True
                        self._push(f'if(typeof _gpBridgeConnect==="function")'
                                   f'_gpBridgeConnect({sj})')
                        self._last_connect_push = now
                        logger.info("Gamepad connected: %s", state['id'])

                    elif now - self._last_connect_push > self._RECONNECT_INTERVAL:
                        self._push(f'if(typeof _gpBridgeConnect==="function")'
                                   f'_gpBridgeConnect({sj})')
                        self._last_connect_push = now

                    elif sj != self._last_json:
                        self._push(f'if(typeof _gpBridgeUpdate==="function")'
                                   f'_gpBridgeUpdate({sj})')

                    self._last_json = sj
                else:
                    if self._was_connected:
                        self._was_connected = False
                        self._last_json = None
                        self._last_connect_push = 0.0
                        self._push('if(typeof _gpBridgeDisconnect==="function")'
                                   '_gpBridgeDisconnect()')
                        logger.info("Gamepad disconnected")

            except Exception as e:
                logger.debug("Gamepad poll error: %s", e)

            time.sleep(1 / 60)   # ~60 Hz
