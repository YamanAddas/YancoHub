"""
YancoHub — pywebview Window
Opens the Flask UI in a native window with JS API bridge for native dialogs
and a standard Windows menu bar.
"""

import sys
import webbrowser
import webview
from webview.menu import Menu, MenuAction, MenuSeparator
from pathlib import Path

from constants import FLASK_PORT, VERSION


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


# ── Menu Callbacks ────────────────────────────────────────────────────────────
# These run in the pywebview main thread. Use evaluate_js to talk to the frontend.

def _js(code: str):
    """Run JS in the active window."""
    w = webview.active_window()
    if w:
        w.evaluate_js(code)


def _menu_rescan():
    _js("fetch('/api/rescan',{method:'POST'}); showToast('Rescanning library...')")


def _menu_settings():
    _js("openSettings()")


def _menu_catbyte():
    _js("toggleCatByte()")


def _menu_fullscreen():
    w = webview.active_window()
    if w:
        w.toggle_fullscreen()


def _menu_reload():
    w = webview.active_window()
    if w:
        w.load_url(f'http://127.0.0.1:{FLASK_PORT}')


def _menu_game_mode():
    _js("if(typeof enterGameMode==='function') enterGameMode()")


def _menu_mood_picker():
    _js("if(typeof openMoodPicker==='function') openMoodPicker()")


def _menu_about():
    _js("openSettings(); setTimeout(()=>{ const t=document.querySelector('[data-tab=\"about\"]'); if(t) t.click(); }, 200)")


def _menu_github():
    webbrowser.open('https://github.com/YamanAddas/YancoHub')


def _menu_report_issue():
    webbrowser.open('https://github.com/YamanAddas/YancoHub/issues')


# ── Menu Structure ────────────────��───────────────────────────────────────────

def _build_menu():
    return [
        Menu('File', [
            MenuAction('Rescan Library', _menu_rescan),
            MenuSeparator(),
            MenuAction('Settings', _menu_settings),
        ]),
        Menu('View', [
            MenuAction('Fullscreen\tF11', _menu_fullscreen),
            MenuAction('Game Mode', _menu_game_mode),
            MenuSeparator(),
            MenuAction('Reload', _menu_reload),
        ]),
        Menu('Games', [
            MenuAction("What Should I Play?", _menu_mood_picker),
            MenuSeparator(),
            MenuAction('CatByte AI', _menu_catbyte),
        ]),
        Menu('Help', [
            MenuAction('GitHub Repository', _menu_github),
            MenuAction('Report an Issue', _menu_report_issue),
            MenuSeparator(),
            MenuAction(f'About YancoHub v{VERSION}', _menu_about),
        ]),
    ]


# ── Window Entry Point ───────────��───────────────────────────────────────────

def main():
    menu = _build_menu()

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
    webview.start(menu=menu, debug='--debug' in sys.argv)


if __name__ == '__main__':
    main()
