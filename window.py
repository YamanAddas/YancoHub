"""
YancoHub — pywebview Window
Opens the Flask UI in a native window with JS API bridge for native dialogs
and a standard Windows menu bar.
"""

import os
import sys
import shutil
import webbrowser
import webview
from webview.menu import Menu, MenuAction, MenuSeparator
from pathlib import Path

from constants import FLASK_PORT, VERSION

APP_DIR = Path(__file__).parent


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


def _win():
    """Get the active pywebview window."""
    return webview.active_window()


# ── File ──────────────────────────────────────────────────────────────────────

def _menu_rescan():
    _js("fetch('/api/rescan',{method:'POST'}); showToast('Rescanning library...')")


def _menu_add_rom_folder():
    _js("""
        (async () => {
            const path = await window.pywebview.api.browse_folder('Select ROM Folder');
            if (!path) return;
            const r = await fetch('/api/rom-dirs', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path})
            });
            if (r.ok) showToast('ROM folder added — rescanning...');
            else showToast('Failed to add folder', 'error');
        })()
    """)


def _menu_add_local_folder():
    _js("""
        (async () => {
            const path = await window.pywebview.api.browse_folder('Select Games Folder');
            if (!path) return;
            const r = await fetch('/api/local-dirs', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path})
            });
            if (r.ok) showToast('Games folder added — rescanning...');
            else showToast('Failed to add folder', 'error');
        })()
    """)


def _menu_settings():
    _js("openSettings()")


def _menu_exit():
    w = _win()
    if w:
        w.destroy()


# ── View ──────────────────────────────────────────────────────────────────────

def _menu_game_mode():
    _js("if(typeof enterGamingMode==='function') enterGamingMode()")


def _menu_fullscreen():
    w = _win()
    if w:
        w.toggle_fullscreen()


def _menu_minimize():
    w = _win()
    if w:
        w.minimize()


def _menu_restore():
    w = _win()
    if w:
        w.restore()


def _menu_on_top():
    w = _win()
    if w:
        w.on_top = not w.on_top
        state = 'on' if w.on_top else 'off'
        _js(f"showToast('Always on top: {state}')")


def _menu_zoom_in():
    _js("document.body.style.zoom = "
        "(parseFloat(document.body.style.zoom||1) + 0.1).toFixed(1)")


def _menu_zoom_out():
    _js("document.body.style.zoom = "
        "Math.max(0.5, (parseFloat(document.body.style.zoom||1) - 0.1)).toFixed(1)")


def _menu_zoom_reset():
    _js("document.body.style.zoom = '1'")


def _menu_reload():
    w = _win()
    if w:
        w.load_url(f'http://127.0.0.1:{FLASK_PORT}')


# ── Games ─────────────────────────────────────────────────────────────────────

def _menu_mood_picker():
    _js("{ const el = document.getElementById('moodOverlay'); "
        "if (el) el.classList.remove('hidden'); }")


def _menu_catbyte():
    _js("if(typeof toggleCatbyte==='function') toggleCatbyte()")


def _menu_clear_art_cache():
    art_dir = APP_DIR / 'cache' / 'artwork'
    if art_dir.is_dir():
        count = sum(1 for f in art_dir.iterdir() if f.is_file())
        shutil.rmtree(art_dir, ignore_errors=True)
        art_dir.mkdir(parents=True, exist_ok=True)
        _js(f"showToast('Cleared {count} cached artwork files — rescan to re-fetch')")
    else:
        _js("showToast('Artwork cache is already empty')")


# ── Help ──────────────────────────────────────────────────────────────────────

def _menu_github():
    webbrowser.open('https://github.com/YamanAddas/YancoHub')


def _menu_report_issue():
    webbrowser.open('https://github.com/YamanAddas/YancoHub/issues')


def _menu_open_logs():
    logs_dir = APP_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)
    os.startfile(str(logs_dir))


def _menu_open_data():
    cache_dir = APP_DIR / 'cache'
    cache_dir.mkdir(exist_ok=True)
    os.startfile(str(cache_dir))


def _menu_about():
    _js("openSettings(); setTimeout(()=>{ "
        "const t=document.querySelector('[data-tab=\"about\"]'); "
        "if(t) t.click(); }, 200)")


# ── Menu Structure ────────────────────────────────────────────────────────────

def _build_menu():
    return [
        Menu('File', [
            MenuAction('Rescan Library', _menu_rescan),
            MenuSeparator(),
            Menu('Import', [
                MenuAction('Add ROM Folder...', _menu_add_rom_folder),
                MenuAction('Add Local Games Folder...', _menu_add_local_folder),
            ]),
            MenuSeparator(),
            MenuAction('Settings', _menu_settings),
            MenuSeparator(),
            MenuAction('Exit', _menu_exit),
        ]),
        Menu('View', [
            MenuAction('Game Mode', _menu_game_mode),
            MenuAction('Fullscreen', _menu_fullscreen),
            MenuSeparator(),
            MenuAction('Minimize', _menu_minimize),
            MenuAction('Restore', _menu_restore),
            MenuAction('Always on Top', _menu_on_top),
            MenuSeparator(),
            MenuAction('Zoom In', _menu_zoom_in),
            MenuAction('Zoom Out', _menu_zoom_out),
            MenuAction('Reset Zoom', _menu_zoom_reset),
            MenuSeparator(),
            MenuAction('Reload', _menu_reload),
        ]),
        Menu('Games', [
            MenuAction('What Should I Play?', _menu_mood_picker),
            MenuSeparator(),
            MenuAction('CatByte AI', _menu_catbyte),
            MenuSeparator(),
            MenuAction('Clear Artwork Cache', _menu_clear_art_cache),
        ]),
        Menu('Help', [
            MenuAction('GitHub Repository', _menu_github),
            MenuAction('Report an Issue', _menu_report_issue),
            MenuSeparator(),
            MenuAction('Open Logs Folder', _menu_open_logs),
            MenuAction('Open Data Folder', _menu_open_data),
            MenuSeparator(),
            MenuAction(f'About YancoHub v{VERSION}', _menu_about),
        ]),
    ]


# ── Window Entry Point ───────────────────────────────────────────────────────

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

    def _on_start():
        """Start the native gamepad bridge after the window is ready."""
        try:
            from gamepad import GamepadBridge
            bridge = GamepadBridge(window)
            bridge.start()
        except Exception as e:
            import logging
            logging.getLogger('yancohub.window').debug(
                "Gamepad bridge failed to start: %s", e)

    webview.start(func=_on_start, menu=menu, debug='--debug' in sys.argv)


if __name__ == '__main__':
    main()
