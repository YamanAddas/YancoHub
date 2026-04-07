"""Tests for startup.py — mock winreg for startup registry operations."""

import sys
from unittest.mock import patch, MagicMock, call

import pytest

import startup


class TestIsStartupEnabled:
    def test_returns_true_when_key_exists(self):
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = (r'C:\path\to\YancoHub.exe --minimized', 1)
        mock_winreg.HKEY_CURRENT_USER = 0x80000001
        mock_winreg.KEY_READ = 0x20019

        with patch.dict('sys.modules', winreg=mock_winreg), \
             patch.object(startup, 'sys') as mock_sys:
            mock_sys.platform = 'win32'
            assert startup.is_startup_enabled() is True

    def test_returns_false_when_key_missing(self):
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = FileNotFoundError
        mock_winreg.HKEY_CURRENT_USER = 0x80000001
        mock_winreg.KEY_READ = 0x20019

        with patch.dict('sys.modules', winreg=mock_winreg), \
             patch.object(startup, 'sys') as mock_sys:
            mock_sys.platform = 'win32'
            assert startup.is_startup_enabled() is False

    def test_returns_false_on_non_windows(self):
        original = startup.sys.platform
        startup.sys.platform = 'linux'
        try:
            assert startup.is_startup_enabled() is False
        finally:
            startup.sys.platform = original


class TestSetStartupEnabled:
    def test_enable_writes_registry(self):
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = 0x80000001
        mock_winreg.KEY_SET_VALUE = 0x0002
        mock_winreg.REG_SZ = 1

        with patch.dict('sys.modules', winreg=mock_winreg), \
             patch.object(startup, 'sys') as mock_sys:
            mock_sys.platform = 'win32'
            mock_sys.executable = r'C:\YancoHub\YancoHub.exe'
            mock_sys.argv = ['app.py']
            mock_sys.frozen = False  # not frozen
            # Need getattr(sys, 'frozen', False) to return False
            result = startup.set_startup_enabled(True)
            assert result is True
            mock_winreg.SetValueEx.assert_called_once()

    def test_disable_deletes_registry(self):
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = 0x80000001
        mock_winreg.KEY_SET_VALUE = 0x0002

        with patch.dict('sys.modules', winreg=mock_winreg), \
             patch.object(startup, 'sys') as mock_sys:
            mock_sys.platform = 'win32'
            result = startup.set_startup_enabled(False)
            assert result is True
            mock_winreg.DeleteValue.assert_called_once()

    def test_returns_false_on_non_windows(self):
        original = startup.sys.platform
        startup.sys.platform = 'linux'
        try:
            assert startup.set_startup_enabled(True) is False
        finally:
            startup.sys.platform = original
