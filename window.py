"""
YancoHub — pywebview Window
Opens the Flask UI in a native window with JS API bridge for native dialogs.
"""

import webview
import sys
from pathlib import Path

from constants import FLASK_PORT


class Api:
    """
    Exposed to JavaScript as window.pywebview.api.*
    Methods here run in the pywebview process (main thread),
    which has access to native OS dialogs that Flask cannot reach.
    """

    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    def browse_folder(self, title: str = 'Select Folder', directory: str = '') -> str | None:
        """Open native Windows folder picker. Returns selected path or None."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=directory or str(Path.home()),
        )
        if result and len(result) > 0:
            return str(result[0])
        return None

    def browse_file(self, title: str = 'Select File', directory: str = '',
                    file_types: tuple = ()) -> str | None:
        """Open native Windows file picker. Returns selected path or None."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=directory or str(Path.home()),
            file_types=file_types or ('All files (*.*)',),
        )
        if result and len(result) > 0:
            return str(result[0])
        return None

    def toggle_fullscreen(self) -> bool:
        """Toggle native fullscreen. Returns new fullscreen state."""
        if not self._window:
            return False
        self._window.toggle_fullscreen()
        return True

    def minimize(self) -> bool:
        """Minimize the window."""
        if not self._window:
            return False
        self._window.minimize()
        return True


api = Api()


def main():
    window = webview.create_window(
        'YancoHub',
        f'http://127.0.0.1:{FLASK_PORT}',
        width=1400,
        height=900,
        min_size=(1024, 600),
        background_color='#060b14',
        text_select=False,
        js_api=api,
    )
    api.set_window(window)
    webview.start(debug='--debug' in sys.argv)


if __name__ == '__main__':
    main()
