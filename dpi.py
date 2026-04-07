"""
YancoHub — DPI Awareness
Enables Per-Monitor V2 DPI awareness on Windows for crisp rendering on high-DPI displays.
Must be called before any window creation (before importing webview).
"""

import sys
import ctypes


def enable_dpi_awareness() -> None:
    """Enable the best available DPI awareness mode.

    Fallback chain:
      1. Per-Monitor V2 (Windows 10 1703+) — best quality
      2. Per-Monitor V1 (Windows 8.1+)
      3. System DPI Aware (Windows Vista+)
    """
    if sys.platform != 'win32':
        return

    try:
        # Per-Monitor V2: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass

    try:
        # Per-Monitor V1: PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass

    try:
        # System DPI aware (fallback)
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass
