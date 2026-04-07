"""
YancoHub — System Tray Icon
Runs pystray in a daemon thread so the app can minimize to tray.
"""

import logging
import threading
from pathlib import Path

logger = logging.getLogger('yancohub.tray')

APP_DIR = Path(__file__).parent
_ICON_PATH = APP_DIR / 'assets' / 'icon.ico'

_icon = None
_thread = None


def start_tray(on_show, on_exit) -> None:
    """Start the system tray icon in a daemon thread.

    Args:
        on_show: callback when user clicks "Show YancoHub"
        on_exit: callback when user clicks "Exit"
    """
    global _icon, _thread

    try:
        import pystray
        from PIL import Image
    except ImportError:
        logger.debug("pystray/Pillow not installed — tray disabled")
        return

    if not _ICON_PATH.exists():
        logger.debug("Tray icon not found at %s", _ICON_PATH)
        return

    try:
        image = Image.open(str(_ICON_PATH))
    except Exception as e:
        logger.debug("Failed to load tray icon: %s", e)
        return

    menu = pystray.Menu(
        pystray.MenuItem('Show YancoHub', on_show, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Exit', on_exit),
    )

    _icon = pystray.Icon('YancoHub', image, 'YancoHub', menu)

    def _run():
        try:
            _icon.run()
        except Exception as e:
            logger.debug("Tray icon error: %s", e)

    _thread = threading.Thread(target=_run, name='tray-icon', daemon=True)
    _thread.start()
    logger.debug("System tray icon started")


def stop_tray() -> None:
    """Stop the tray icon cleanly."""
    global _icon
    if _icon:
        try:
            _icon.stop()
        except Exception:
            pass
        _icon = None
