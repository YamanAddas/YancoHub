"""Tests for gamepad.py — native gamepad bridge (HID + XInput + WinMM)."""

import ctypes
from unittest.mock import patch, MagicMock
import pytest

from gamepad import (
    _btn, _norm_axis, _pov_to_dpad, _is_playstation,
    _hid_buttons_to_w3c, _hid_sticks_to_axes,
    _read_xinput, _read_winmm, read_gamepad, gamepad_diagnostics,
    _HIDReader, _KNOWN_HID, _HID_DPAD,
    STD_BUTTONS, STD_AXES,
    XINPUT_STATE, XINPUT_GAMEPAD, JOYINFOEX, JOYCAPSW,
    GamepadBridge,
)


# ── Utility functions ──────────────────────────────────────────────────────

class TestBtn:
    def test_pressed(self):
        assert _btn(True) == {'pressed': True, 'value': 1.0}

    def test_released(self):
        assert _btn(False) == {'pressed': False, 'value': 0.0}


class TestNormAxis:
    def test_center(self):
        assert _norm_axis(32767, 0, 65535) == pytest.approx(0.0, abs=0.001)

    def test_min(self):
        assert _norm_axis(0, 0, 65535) == pytest.approx(-1.0, abs=0.001)

    def test_max(self):
        assert _norm_axis(65535, 0, 65535) == pytest.approx(1.0, abs=0.001)

    def test_equal_range_returns_zero(self):
        assert _norm_axis(100, 100, 100) == 0.0

    def test_inverted_range_returns_zero(self):
        assert _norm_axis(50, 100, 50) == 0.0


class TestPovToDpad:
    def test_centered(self):
        assert _pov_to_dpad(0xFFFF) == (False, False, False, False)

    def test_up(self):
        up, down, left, right = _pov_to_dpad(0)
        assert up and not down and not left and not right

    def test_right(self):
        up, down, left, right = _pov_to_dpad(9000)
        assert right and not left

    def test_down(self):
        up, down, left, right = _pov_to_dpad(18000)
        assert down and not up

    def test_left(self):
        up, down, left, right = _pov_to_dpad(27000)
        assert left and not right

    def test_up_right_diagonal(self):
        up, down, left, right = _pov_to_dpad(4500)
        assert up and right

    def test_out_of_range(self):
        assert _pov_to_dpad(99999) == (False, False, False, False)


class TestIsPlaystation:
    def test_wireless_controller(self):
        assert _is_playstation('Wireless Controller', 14)

    def test_dualsense(self):
        assert _is_playstation('DualSense Wireless', 14)

    def test_dualshock(self):
        assert _is_playstation('DualShock 4', 13)

    def test_high_button_count(self):
        assert _is_playstation('Some Controller', 13)

    def test_xbox_controller(self):
        assert not _is_playstation('Xbox Controller', 10)

    def test_generic_controller(self):
        assert not _is_playstation('Generic Joystick', 8)


# ── HID report parsing ───────────────────────────────────────────────────

class TestHIDButtonsToW3C:
    """Test HID button byte → W3C standard mapping."""

    def test_no_buttons_pressed(self):
        # btn0=0x08 means dpad=8 (released), no face buttons
        buttons = _hid_buttons_to_w3c(0x08, 0x00, 0x00, 0, 0)
        assert len(buttons) == STD_BUTTONS
        for b in buttons:
            assert not b['pressed']

    def test_cross_maps_to_a(self):
        buttons = _hid_buttons_to_w3c(0x28, 0x00, 0x00, 0, 0)  # cross=0x20, dpad=8
        assert buttons[0]['pressed']   # A
        assert not buttons[1]['pressed']

    def test_circle_maps_to_b(self):
        buttons = _hid_buttons_to_w3c(0x48, 0x00, 0x00, 0, 0)  # circle=0x40, dpad=8
        assert buttons[1]['pressed']

    def test_square_maps_to_x(self):
        buttons = _hid_buttons_to_w3c(0x18, 0x00, 0x00, 0, 0)  # square=0x10, dpad=8
        assert buttons[2]['pressed']

    def test_triangle_maps_to_y(self):
        buttons = _hid_buttons_to_w3c(0x88, 0x00, 0x00, 0, 0)  # triangle=0x80, dpad=8
        assert buttons[3]['pressed']

    def test_l1_r1(self):
        buttons = _hid_buttons_to_w3c(0x08, 0x03, 0x00, 0, 0)  # L1+R1
        assert buttons[4]['pressed']   # LB
        assert buttons[5]['pressed']   # RB

    def test_triggers_analog(self):
        buttons = _hid_buttons_to_w3c(0x08, 0x00, 0x00, 200, 100)
        assert buttons[6]['pressed']   # LT pressed (200/255 > 0.12)
        assert buttons[6]['value'] == pytest.approx(200 / 255, abs=0.01)
        assert buttons[7]['pressed']   # RT pressed
        assert buttons[7]['value'] == pytest.approx(100 / 255, abs=0.01)

    def test_triggers_below_threshold(self):
        buttons = _hid_buttons_to_w3c(0x08, 0x00, 0x00, 10, 0)
        assert not buttons[6]['pressed']  # 10/255 ≈ 0.039 < 0.12
        assert not buttons[7]['pressed']

    def test_create_options_l3_r3(self):
        buttons = _hid_buttons_to_w3c(0x08, 0xF0, 0x00, 0, 0)
        assert buttons[8]['pressed']    # Create → Select
        assert buttons[9]['pressed']    # Options → Start
        assert buttons[10]['pressed']   # L3 → LS
        assert buttons[11]['pressed']   # R3 → RS

    def test_dpad_up(self):
        buttons = _hid_buttons_to_w3c(0x00, 0x00, 0x00, 0, 0)  # dpad=0 (N)
        assert buttons[12]['pressed']      # Up
        assert not buttons[13]['pressed']  # Not down

    def test_dpad_down(self):
        buttons = _hid_buttons_to_w3c(0x04, 0x00, 0x00, 0, 0)  # dpad=4 (S)
        assert buttons[13]['pressed']      # Down
        assert not buttons[12]['pressed']

    def test_dpad_left(self):
        buttons = _hid_buttons_to_w3c(0x06, 0x00, 0x00, 0, 0)  # dpad=6 (W)
        assert buttons[14]['pressed']      # Left

    def test_dpad_right(self):
        buttons = _hid_buttons_to_w3c(0x02, 0x00, 0x00, 0, 0)  # dpad=2 (E)
        assert buttons[15]['pressed']      # Right

    def test_dpad_diagonal(self):
        buttons = _hid_buttons_to_w3c(0x01, 0x00, 0x00, 0, 0)  # dpad=1 (NE)
        assert buttons[12]['pressed']   # Up
        assert buttons[15]['pressed']   # Right

    def test_ps_button(self):
        buttons = _hid_buttons_to_w3c(0x08, 0x00, 0x01, 0, 0)
        assert buttons[16]['pressed']   # Home

    def test_buttons_are_independent(self):
        buttons = _hid_buttons_to_w3c(0x08, 0x00, 0x00, 0, 0)
        buttons[0]['pressed'] = True
        assert not buttons[1]['pressed']


class TestHIDSticksToAxes:
    def test_center(self):
        axes = _hid_sticks_to_axes(128, 128, 128, 128)
        assert len(axes) == STD_AXES
        for a in axes:
            assert a == pytest.approx(0.0, abs=0.01)

    def test_full_left(self):
        axes = _hid_sticks_to_axes(0, 128, 128, 128)
        assert axes[0] == pytest.approx(-1.0, abs=0.01)

    def test_full_right(self):
        axes = _hid_sticks_to_axes(255, 128, 128, 128)
        assert axes[0] == pytest.approx(1.0, abs=0.01)

    def test_full_down(self):
        axes = _hid_sticks_to_axes(128, 255, 128, 128)
        assert axes[1] == pytest.approx(1.0, abs=0.01)

    def test_clamped_range(self):
        axes = _hid_sticks_to_axes(0, 0, 255, 255)
        for a in axes:
            assert -1.0 <= a <= 1.0


class TestHIDDpadLookup:
    def test_all_directions_defined(self):
        for i in range(8):
            assert i in _HID_DPAD
            up, down, left, right = _HID_DPAD[i]
            assert isinstance(up, bool)

    def test_released_not_in_table(self):
        assert 8 not in _HID_DPAD


# ── HID Reader ────────────────────────────────────────────────────────────

class TestHIDReader:
    def test_read_returns_none_without_hidapi(self):
        reader = _HIDReader()
        with patch('gamepad._hid_available', False):
            assert reader.read() is None

    def test_connected_property(self):
        reader = _HIDReader()
        assert not reader.connected

    def test_diagnostics_without_hidapi(self):
        reader = _HIDReader()
        with patch('gamepad._hid_available', False):
            diag = reader.diagnostics()
            assert diag['available'] is False
            assert diag['devices'] == []

    def test_parse_dualsense_usb_report(self):
        """Simulate a DualSense USB report (ID 0x01)."""
        reader = _HIDReader()
        reader._type = 'dualsense'
        reader._name = 'DualSense'

        # Build a 64-byte USB report: ID=0x01, sticks centered, Cross pressed
        data = bytearray(64)
        data[0] = 0x01       # report ID
        data[1] = 128        # LX center
        data[2] = 128        # LY center
        data[3] = 128        # RX center
        data[4] = 128        # RY center
        data[5] = 0          # L2
        data[6] = 0          # R2
        data[7] = 0          # counter
        data[8] = 0x28       # btn0: Cross(0x20) + dpad released(0x08)
        data[9] = 0x00       # btn1
        data[10] = 0x00      # btn2

        result = reader._parse(bytes(data))
        assert result is not None
        assert result['buttons'][0]['pressed']    # Cross → A
        assert not result['buttons'][1]['pressed']
        assert len(result['axes']) == STD_AXES

    def test_parse_dualsense_bt_full_report(self):
        """Simulate a DualSense BT full report (ID 0x31)."""
        reader = _HIDReader()
        reader._type = 'dualsense'
        reader._name = 'DualSense'

        data = bytearray(78)
        data[0] = 0x31       # report ID
        data[1] = 0x00       # BT header
        data[2] = 128        # LX
        data[3] = 0          # LY full up
        data[4] = 128        # RX
        data[5] = 128        # RY
        data[6] = 255        # L2 full
        data[7] = 0          # R2
        data[8] = 0          # counter
        data[9] = 0x08       # btn0: dpad released only
        data[10] = 0x20      # btn1: Options
        data[11] = 0x00      # btn2

        result = reader._parse(bytes(data))
        assert result is not None
        assert result['axes'][1] == pytest.approx(-1.0, abs=0.01)  # LY full up
        assert result['buttons'][6]['pressed']    # L2 full
        assert result['buttons'][6]['value'] == pytest.approx(1.0, abs=0.01)
        assert result['buttons'][9]['pressed']    # Options → Start

    def test_parse_ds4_usb_report(self):
        """Simulate a DualShock 4 USB report (ID 0x01)."""
        reader = _HIDReader()
        reader._type = 'ds4'
        reader._name = 'DualShock 4'

        data = bytearray(64)
        data[0] = 0x01       # report ID
        data[1] = 128        # LX
        data[2] = 128        # LY
        data[3] = 0          # RX full left
        data[4] = 128        # RY
        data[5] = 0x48       # btn0: Circle(0x40) + dpad released(0x08)
        data[6] = 0x00       # btn1
        data[7] = 0x00       # btn2
        data[8] = 0          # L2
        data[9] = 200        # R2

        result = reader._parse(bytes(data))
        assert result is not None
        assert result['buttons'][1]['pressed']    # Circle → B
        assert result['axes'][2] == pytest.approx(-1.0, abs=0.01)  # RX full left
        assert result['buttons'][7]['value'] == pytest.approx(200 / 255, abs=0.01)  # R2

    def test_parse_ds4_bt_report(self):
        """Simulate a DualShock 4 BT report (ID 0x11)."""
        reader = _HIDReader()
        reader._type = 'ds4'
        reader._name = 'DualShock 4'

        data = bytearray(78)
        data[0] = 0x11       # report ID
        data[1] = 0x00       # BT header 1
        data[2] = 0x00       # BT header 2
        data[3] = 128        # LX
        data[4] = 128        # LY
        data[5] = 128        # RX
        data[6] = 128        # RY
        data[7] = 0x00       # btn0: dpad=0 (up)
        data[8] = 0x01       # btn1: L1
        data[9] = 0x00       # btn2
        data[10] = 0         # L2
        data[11] = 0         # R2

        result = reader._parse(bytes(data))
        assert result is not None
        assert result['buttons'][12]['pressed']   # D-pad up
        assert result['buttons'][4]['pressed']    # L1 → LB

    def test_parse_unknown_report_returns_none(self):
        reader = _HIDReader()
        reader._type = 'dualsense'
        reader._name = 'DualSense'
        assert reader._parse(bytes([0xFF, 0, 0])) is None

    def test_parse_short_report_returns_none(self):
        reader = _HIDReader()
        reader._type = 'dualsense'
        reader._name = 'DualSense'
        assert reader._parse(bytes([0x01, 0, 0])) is None


class TestKnownHID:
    def test_dualsense_in_table(self):
        assert (0x054C, 0x0CE6) in _KNOWN_HID

    def test_dualsense_edge_in_table(self):
        assert (0x054C, 0x0DF2) in _KNOWN_HID

    def test_ds4_v1_in_table(self):
        assert (0x054C, 0x05C4) in _KNOWN_HID

    def test_ds4_v2_in_table(self):
        assert (0x054C, 0x09CC) in _KNOWN_HID


# ── XInput reader ──────────────────────────────────────────────────────────

class TestReadXInput:
    def test_returns_none_when_no_dll(self):
        with patch('gamepad._xinput', None):
            assert _read_xinput(0) is None

    def test_returns_none_on_error(self):
        mock_dll = MagicMock()
        mock_dll.XInputGetState.return_value = 1167
        with patch('gamepad._xinput', mock_dll):
            assert _read_xinput(0) is None

    def test_reads_xinput_state(self):
        mock_dll = MagicMock()

        def fake_get_state(index, state_ref):
            state = state_ref._obj if hasattr(state_ref, '_obj') else state_ref
            state.Gamepad.wButtons = 0x1000  # A button
            state.Gamepad.bLeftTrigger = 128
            state.Gamepad.bRightTrigger = 0
            state.Gamepad.sThumbLX = 16383
            state.Gamepad.sThumbLY = -16383
            state.Gamepad.sThumbRX = 0
            state.Gamepad.sThumbRY = 0
            return 0

        mock_dll.XInputGetState.side_effect = fake_get_state
        with patch('gamepad._xinput', mock_dll):
            result = _read_xinput(0)

        assert result is not None
        assert result['mapping'] == 'standard'
        assert result['buttons'][0]['pressed']
        assert result['buttons'][6]['value'] == pytest.approx(128 / 255, abs=0.01)
        assert len(result['buttons']) == STD_BUTTONS
        assert len(result['axes']) == STD_AXES

    def test_buttons_are_independent_objects(self):
        mock_dll = MagicMock()
        mock_dll.XInputGetState.return_value = 0
        with patch('gamepad._xinput', mock_dll):
            result = _read_xinput(0)
        result['buttons'][0]['pressed'] = True
        assert not result['buttons'][1]['pressed']


# ── WinMM reader ───────────────────────────────────────────────────────────

class TestReadWinMM:
    def test_returns_none_when_no_dll(self):
        with patch('gamepad._winmm', None):
            assert _read_winmm(0) is None

    def test_returns_none_on_error(self):
        mock = MagicMock()
        mock.joyGetPosEx.return_value = 1
        with patch('gamepad._winmm', mock):
            assert _read_winmm(0) is None


# ── W3C output structure ──────────────────────────────────────────────────

class TestOutputStructure:
    def _make_state(self):
        state = read_gamepad()
        if state is None:
            state = {
                'id': 'Test Controller',
                'index': 0,
                'mapping': 'standard',
                'buttons': [_btn(False) for _ in range(STD_BUTTONS)],
                'axes': [0.0] * STD_AXES,
            }
        return state

    def test_has_required_fields(self):
        state = self._make_state()
        for key in ('id', 'index', 'mapping', 'buttons', 'axes'):
            assert key in state

    def test_button_count(self):
        assert len(self._make_state()['buttons']) == STD_BUTTONS

    def test_axis_count(self):
        assert len(self._make_state()['axes']) == STD_AXES

    def test_button_structure(self):
        for i, btn in enumerate(self._make_state()['buttons']):
            assert 'pressed' in btn
            assert 'value' in btn
            assert isinstance(btn['pressed'], bool)
            assert isinstance(btn['value'], (int, float))

    def test_axis_range(self):
        for i, val in enumerate(self._make_state()['axes']):
            assert -1.0 <= val <= 1.0


# ── GamepadBridge ──────────────────────────────────────────────────────────

class TestGamepadBridge:
    def test_start_stop(self):
        mock_window = MagicMock()
        bridge = GamepadBridge(mock_window)
        bridge.start()
        assert bridge._running
        bridge.stop()
        assert not bridge._running

    def test_double_start_is_safe(self):
        mock_window = MagicMock()
        bridge = GamepadBridge(mock_window)
        bridge.start()
        bridge.start()
        bridge.stop()

    def test_push_handles_exceptions(self):
        mock_window = MagicMock()
        mock_window.evaluate_js.side_effect = RuntimeError("window gone")
        bridge = GamepadBridge(mock_window)
        assert bridge._push('test()') is False

    def test_push_returns_true_on_success(self):
        mock_window = MagicMock()
        bridge = GamepadBridge(mock_window)
        assert bridge._push('test()') is True


# ── Diagnostics ──────────────────────────────────────────────────────────

class TestGamepadDiagnostics:
    def test_returns_required_keys(self):
        result = gamepad_diagnostics()
        assert 'hid' in result
        assert 'xinput_available' in result
        assert 'winmm_available' in result
        assert 'detected' in result
        assert isinstance(result['detected'], bool)

    def test_hid_section_has_keys(self):
        result = gamepad_diagnostics()
        hid = result['hid']
        assert 'available' in hid
        assert 'connected' in hid
        assert 'devices' in hid

    def test_no_crash_with_mocked_apis(self):
        with patch('gamepad._xinput', None), patch('gamepad._winmm', None):
            result = gamepad_diagnostics()
            assert result['xinput_available'] is False
            assert result['winmm_available'] is False
