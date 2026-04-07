"""Tests for singleinstance.py — mutex acquisition and release."""

import sys
from unittest.mock import patch, MagicMock

import pytest


class TestAcquireInstanceLock:
    def test_returns_true_on_first_instance(self):
        """First call should succeed (no competing process)."""
        mock_kernel = MagicMock()
        mock_kernel.CreateMutexW.return_value = 12345

        with patch.dict(sys.modules, {}), \
             patch('singleinstance._kernel32', mock_kernel), \
             patch('ctypes.get_last_error', return_value=0):
            from singleinstance import acquire_instance_lock
            assert acquire_instance_lock() is True

    def test_returns_false_when_already_running(self):
        """Should return False when ERROR_ALREADY_EXISTS (183)."""
        mock_kernel = MagicMock()
        mock_kernel.CreateMutexW.return_value = 12345

        with patch.dict(sys.modules, {}), \
             patch('singleinstance._kernel32', mock_kernel), \
             patch('ctypes.get_last_error', return_value=183):
            from singleinstance import acquire_instance_lock
            assert acquire_instance_lock() is False

    def test_non_windows_always_true(self):
        """On non-Windows platforms, always return True."""
        with patch('singleinstance.sys') as mock_sys:
            mock_sys.platform = 'linux'
            from singleinstance import acquire_instance_lock
            # Re-import to use patched sys
            import singleinstance
            original = singleinstance.sys.platform
            singleinstance.sys.platform = 'linux'
            try:
                assert singleinstance.acquire_instance_lock() is True
            finally:
                singleinstance.sys.platform = original


class TestReleaseInstanceLock:
    def test_release_clears_handle(self):
        """Release should call CloseHandle and clear the global."""
        import singleinstance
        mock_kernel = MagicMock()

        original_handle = singleinstance._mutex_handle
        original_kernel = getattr(singleinstance, '_kernel32', None)

        singleinstance._mutex_handle = 99999
        singleinstance._kernel32 = mock_kernel

        try:
            singleinstance.release_instance_lock()
            mock_kernel.CloseHandle.assert_called_once_with(99999)
            assert singleinstance._mutex_handle is None
        finally:
            singleinstance._mutex_handle = original_handle
            if original_kernel is not None:
                singleinstance._kernel32 = original_kernel

    def test_release_noop_when_no_handle(self):
        """Release with no handle should not raise."""
        import singleinstance
        original = singleinstance._mutex_handle
        singleinstance._mutex_handle = None
        try:
            singleinstance.release_instance_lock()  # Should not raise
        finally:
            singleinstance._mutex_handle = original
