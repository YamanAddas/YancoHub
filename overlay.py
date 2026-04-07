"""
YancoHub — CatByte Game Overlay
Manages a transparent, always-on-top pywebview window for in-game CatByte chat.
Uses Win32 RegisterHotKey (F10) to toggle visibility even when a game has focus.
"""

import ctypes
import ctypes.wintypes
import logging
import threading

import webview

from constants import FLASK_PORT

logger = logging.getLogger('yancohub.overlay')

# Win32 constants
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
VK_F10 = 0x79
HOTKEY_ID = 0xBFFF  # Unique ID for our hotkey

# Window extended styles
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080  # Hide from taskbar/alt-tab
WS_EX_NOACTIVATE = 0x08000000  # Don't steal focus from game

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

_overlay_window = None
_hotkey_thread = None
_stop_event = threading.Event()
_visible = False
_lock = threading.Lock()


def _apply_window_flags(window) -> None:
    """Apply WS_EX_TOOLWINDOW and WS_EX_NOACTIVATE to hide from taskbar
    and prevent stealing focus from the game."""
    try:
        hwnd = window.native_handle
        if not hwnd:
            return
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        logger.debug("Applied overlay window flags (TOOLWINDOW | NOACTIVATE)")
    except Exception as e:
        logger.debug("Failed to apply overlay window flags: %s", e)


def _hotkey_listener() -> None:
    """Background thread that registers F10 as a global hotkey and listens
    for it via the Windows message pump."""
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, VK_F10):
        logger.warning("Failed to register F10 hotkey (error %d)", kernel32.GetLastError())
        return

    logger.info("F10 global hotkey registered for CatByte overlay")
    msg = ctypes.wintypes.MSG()

    try:
        while not _stop_event.is_set():
            # PeekMessage with PM_REMOVE — non-blocking check
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    toggle_overlay()
            else:
                # Yield CPU — check every 50ms
                _stop_event.wait(0.05)
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        logger.info("F10 global hotkey unregistered")


def toggle_overlay() -> None:
    """Toggle overlay window visibility."""
    global _visible
    with _lock:
        if _overlay_window is None:
            return
        try:
            if _visible:
                _overlay_window.hide()
                _visible = False
                logger.debug("Overlay hidden")
            else:
                _overlay_window.show()
                _overlay_window.on_top = True
                _visible = True
                _overlay_window.evaluate_js("if(typeof onOverlayShow==='function') onOverlayShow()")
                logger.debug("Overlay shown")
        except Exception as e:
            logger.debug("toggle_overlay error: %s", e)


def create_overlay_window(js_api=None) -> None:
    """Create the overlay pywebview window (hidden initially).
    Must be called BEFORE webview.start().
    Pass the same js_api used by the main window so pywebview.api is available."""
    global _overlay_window
    # Position on the right edge of the primary monitor
    try:
        screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    except Exception:
        screen_w = 1920

    screen_h = 0
    try:
        screen_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    except Exception:
        screen_h = 1080

    overlay_w = 400
    overlay_h = screen_h - 80  # flush top-to-near-bottom

    _overlay_window = webview.create_window(
        'CatByte Overlay',
        f'http://127.0.0.1:{FLASK_PORT}/overlay',
        width=overlay_w,
        height=overlay_h,
        x=screen_w - overlay_w,
        y=0,
        resizable=True,
        frameless=True,
        on_top=True,
        hidden=True,
        background_color='#060b14',
        text_select=True,
        js_api=js_api,
    )
    logger.info("CatByte overlay window created")


def start_overlay() -> None:
    """Start the hotkey listener thread and apply window flags.
    Must be called AFTER webview.start() (from a started callback)."""
    global _hotkey_thread

    # Apply extended window styles
    if _overlay_window:
        _apply_window_flags(_overlay_window)

    # Start hotkey listener
    _stop_event.clear()
    _hotkey_thread = threading.Thread(
        target=_hotkey_listener,
        name='overlay-hotkey',
        daemon=True,
    )
    _hotkey_thread.start()


def stop_overlay() -> None:
    """Stop the hotkey listener and destroy the overlay window."""
    global _overlay_window, _visible
    _stop_event.set()
    with _lock:
        if _overlay_window:
            try:
                _overlay_window.destroy()
            except Exception:
                pass
            _overlay_window = None
            _visible = False
    logger.info("CatByte overlay stopped")
