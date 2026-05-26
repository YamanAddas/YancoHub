"""
YancoHub — Single Instance Enforcement
Uses a Windows named mutex to prevent multiple instances from running.
The mutex is automatically released by Windows when the process exits (even on crash).
"""

import sys
import ctypes
from ctypes import wintypes

logger = None  # Lazy — logging may not be configured when this runs

_MUTEX_NAME = 'YancoHub_SingleInstance_Mutex'
_ERROR_ALREADY_EXISTS = 183

_mutex_handle = None

if sys.platform == 'win32':
    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.CreateMutexW.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL

    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
    _user32.MessageBoxW.restype = ctypes.c_int


def acquire_instance_lock() -> bool:
    """Try to acquire the single-instance mutex.

    Returns True if this is the first instance.
    Returns False if another instance is already running.
    """
    global _mutex_handle
    if sys.platform != 'win32':
        return True  # Non-Windows: skip

    _mutex_handle = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS


def release_instance_lock() -> None:
    """Release the mutex (called on shutdown, also auto-released on exit)."""
    global _mutex_handle
    if _mutex_handle and sys.platform == 'win32':
        _kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None


def show_already_running_message() -> None:
    """Show a native Windows MessageBox informing the user."""
    if sys.platform != 'win32':
        print("[YancoHub] Already running.")
        return
    _MB_ICONINFORMATION = 0x00000040
    _user32.MessageBoxW(
        None,
        "YancoHub is already running.\n\nCheck your taskbar.",
        "YancoHub",
        _MB_ICONINFORMATION,
    )
