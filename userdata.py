"""
YancoHub User Data — Persistent storage for play time, collections, favorites, settings.
"""

import json
import time
import logging
from pathlib import Path

logger = logging.getLogger('yancohub.userdata')

DATA_FILE = Path(__file__).parent / 'userdata.json'

DEFAULT_DATA = {
    'sessions': {},       # game_id → {total_seconds, last_played, session_count, active_since}
    'collections': {},    # name → [game_id, ...]
    'favorites': [],      # [game_id, ...]
    'hidden_systems': [], # [system_id, ...]
    'local_dirs': [],     # [path, ...]
    'rom_dirs': [],       # [path, ...]
    'accounts': {
        'steam': {
            'api_key': '',
            'steam_id': '',
            'persona_name': '',
            'connected': False,
        },
        'gog_galaxy': {
            'enabled': False,    # Auto-detected, user can toggle
            'db_path': '',       # Auto-filled if found
        },
    },
    'settings': {
        'retroarch_path': '',
        'show_uninstalled': True,  # Show games from accounts even if not installed
    },
}


class UserData:
    def __init__(self, data_file=None):
        self.data_file = data_file or DATA_FILE
        self.data = self._load()
        self._cleanup_stale_sessions()

    def _load(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Merge with defaults for new fields
                for key, default in DEFAULT_DATA.items():
                    if key not in data:
                        data[key] = default
                return data
            except Exception as e:
                logger.error(f"Failed to load userdata: {e}")
        return json.loads(json.dumps(DEFAULT_DATA))

    def _save(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save userdata: {e}")

    def _cleanup_stale_sessions(self):
        """Clear any sessions that were active from a previous crash."""
        for game_id, session in self.data['sessions'].items():
            if session.get('active_since'):
                elapsed = time.time() - session['active_since']
                session['total_seconds'] = session.get('total_seconds', 0) + elapsed
                session['active_since'] = None
                logger.info(f"Cleaned stale session for {game_id} ({elapsed:.0f}s)")
        self._save()

    # ── Play Sessions ───────────────────────────────────────────────────────

    def session_start(self, game_id):
        """Start a play session. Ends any other active session first."""
        # End other active sessions
        for gid, session in self.data['sessions'].items():
            if session.get('active_since') and gid != game_id:
                self.session_end(gid)

        if game_id not in self.data['sessions']:
            self.data['sessions'][game_id] = {
                'total_seconds': 0,
                'last_played': None,
                'session_count': 0,
                'active_since': None,
            }

        self.data['sessions'][game_id]['active_since'] = time.time()
        self.data['sessions'][game_id]['last_played'] = time.time()
        self.data['sessions'][game_id]['session_count'] += 1
        self._save()

    def session_end(self, game_id):
        """End a play session."""
        session = self.data['sessions'].get(game_id)
        if not session or not session.get('active_since'):
            return

        elapsed = time.time() - session['active_since']
        session['total_seconds'] += elapsed
        session['active_since'] = None
        session['last_played'] = time.time()
        self._save()
        logger.info(f"Session ended for {game_id}: {elapsed:.0f}s")

    def get_playtime(self, game_id=None):
        """Get play time data."""
        if game_id:
            session = self.data['sessions'].get(game_id, {})
            total = session.get('total_seconds', 0)
            if session.get('active_since'):
                total += time.time() - session['active_since']
            return {
                'total_hours': round(total / 3600, 1),
                'last_played': session.get('last_played'),
                'session_count': session.get('session_count', 0),
            }
        return {
            gid: {
                'total_hours': round(s.get('total_seconds', 0) / 3600, 1),
                'last_played': s.get('last_played'),
                'session_count': s.get('session_count', 0),
            }
            for gid, s in self.data['sessions'].items()
        }

    def get_last_played(self):
        """Get the most recently played game ID."""
        recent = None
        recent_time = 0
        for gid, session in self.data['sessions'].items():
            lp = session.get('last_played', 0) or 0
            if lp > recent_time:
                recent_time = lp
                recent = gid
        return recent

    def get_active_game(self):
        """Get currently active game ID, if any."""
        for gid, session in self.data['sessions'].items():
            if session.get('active_since'):
                return gid
        return None

    # ── Collections ─────────────────────────────────────────────────────────

    def get_collections(self):
        return dict(self.data['collections'])

    def create_collection(self, name):
        if name not in self.data['collections']:
            self.data['collections'][name] = []
            self._save()
            return True
        return False

    def delete_collection(self, name):
        if name in self.data['collections']:
            del self.data['collections'][name]
            self._save()
            return True
        return False

    def add_to_collection(self, name, game_id):
        if name in self.data['collections']:
            if game_id not in self.data['collections'][name]:
                self.data['collections'][name].append(game_id)
                self._save()
            return True
        return False

    def remove_from_collection(self, name, game_id):
        if name in self.data['collections'] and game_id in self.data['collections'][name]:
            self.data['collections'][name].remove(game_id)
            self._save()
            return True
        return False

    # ── Favorites ───────────────────────────────────────────────────────────

    def get_favorites(self):
        return list(self.data['favorites'])

    def toggle_favorite(self, game_id):
        if game_id in self.data['favorites']:
            self.data['favorites'].remove(game_id)
            self._save()
            return False
        else:
            self.data['favorites'].append(game_id)
            self._save()
            return True

    # ── Hidden Systems ──────────────────────────────────────────────────────

    def get_hidden_systems(self):
        return list(self.data['hidden_systems'])

    def toggle_hidden_system(self, system):
        if system in self.data['hidden_systems']:
            self.data['hidden_systems'].remove(system)
            self._save()
            return False
        else:
            self.data['hidden_systems'].append(system)
            self._save()
            return True

    # ── Local & ROM Directories ─────────────────────────────────────────────

    def get_local_dirs(self):
        return list(self.data['local_dirs'])

    def add_local_dir(self, path):
        if path not in self.data['local_dirs']:
            self.data['local_dirs'].append(path)
            self._save()
        return self.data['local_dirs']

    def remove_local_dir(self, path):
        if path in self.data['local_dirs']:
            self.data['local_dirs'].remove(path)
            self._save()
        return self.data['local_dirs']

    def get_rom_dirs(self):
        return list(self.data['rom_dirs'])

    def add_rom_dir(self, path):
        if path not in self.data['rom_dirs']:
            self.data['rom_dirs'].append(path)
            self._save()
        return self.data['rom_dirs']

    def remove_rom_dir(self, path):
        if path in self.data['rom_dirs']:
            self.data['rom_dirs'].remove(path)
            self._save()
        return self.data['rom_dirs']

    # ── Accounts ────────────────────────────────────────────────────────────

    def get_accounts(self):
        return dict(self.data.get('accounts', {}))

    def get_steam_account(self):
        return dict(self.data.get('accounts', {}).get('steam', {}))

    def set_steam_account(self, api_key, steam_id, persona_name=''):
        self.data.setdefault('accounts', {})['steam'] = {
            'api_key': api_key,
            'steam_id': steam_id,
            'persona_name': persona_name,
            'connected': True,
        }
        self._save()

    def disconnect_steam_account(self):
        self.data.setdefault('accounts', {})['steam'] = {
            'api_key': '',
            'steam_id': '',
            'persona_name': '',
            'connected': False,
        }
        self._save()

    def get_gog_galaxy_config(self):
        return dict(self.data.get('accounts', {}).get('gog_galaxy', {}))

    def set_gog_galaxy_enabled(self, enabled, db_path=''):
        self.data.setdefault('accounts', {})['gog_galaxy'] = {
            'enabled': enabled,
            'db_path': db_path,
        }
        self._save()

    # ── Settings ────────────────────────────────────────────────────────────

    def get_settings(self):
        return dict(self.data.get('settings', {}))

    def update_settings(self, updates):
        self.data.setdefault('settings', {}).update(updates)
        self._save()
