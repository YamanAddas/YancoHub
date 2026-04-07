r"""
YancoHub — Windows Startup Registration
Uses winreg to add/remove YancoHub from Windows startup (HKCU\...\Run).
"""

import sys
import logging

logger = logging.getLogger('yancohub.startup')

_REG_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
_APP_NAME = 'YancoHub'


def _get_exe_path() -> str:
    """Get the path to the current executable."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    # Running as script — use pythonw to avoid console window
    return f'"{sys.executable}" "{sys.argv[0]}"'


def is_startup_enabled() -> bool:
    """Check if YancoHub is registered to launch on Windows startup."""
    if sys.platform != 'win32':
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        logger.debug("Failed to read startup registry: %s", e)
        return False


def set_startup_enabled(enabled: bool) -> bool:
    """Add or remove YancoHub from Windows startup.

    Returns True on success, False on failure.
    """
    if sys.platform != 'win32':
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0,
                             winreg.KEY_SET_VALUE)
        try:
            if enabled:
                exe = _get_exe_path()
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ,
                                  f'{exe} --minimized')
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass  # Already removed
        finally:
            winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.debug("Failed to set startup registry: %s", e)
        return False
