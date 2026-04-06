"""
YancoHub Accounts — Connect to game store accounts to fetch full libraries.

Supports:
  - Steam Web API (API key + Steam ID) → all owned games
  - GOG Galaxy 2.0 database → all games from all connected platforms
  - Epic Games local catalog cache → all owned games (no third-party tools needed)
"""

import os
import json
import base64
import logging
import sqlite3
import requests
from pathlib import Path
from constants import STEAM_CDN

logger = logging.getLogger('yancohub.accounts')

STEAM_API_BASE = "https://api.steampowered.com"


# ── Steam Web API ───────────────────────────────────────────────────────────

class SteamAccount:
    """Fetch full owned game library via Steam Web API."""

    def __init__(self, api_key, steam_id):
        self.api_key = api_key
        self.steam_id = steam_id

    def validate(self):
        """Check if the API key and Steam ID are valid."""
        try:
            resp = requests.get(
                f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v2/",
                params={'key': self.api_key, 'steamids': self.steam_id},
                timeout=10,
            )
            if resp.status_code == 403:
                return {'valid': False, 'error': 'Invalid API key'}
            if resp.status_code != 200:
                return {'valid': False, 'error': f'HTTP {resp.status_code}'}

            data = resp.json()
            players = data.get('response', {}).get('players', [])
            if not players:
                return {'valid': False, 'error': 'Steam ID not found'}

            player = players[0]
            return {
                'valid': True,
                'persona_name': player.get('personaname', ''),
                'avatar': player.get('avatarmedium', ''),
                'profile_url': player.get('profileurl', ''),
            }
        except requests.ConnectionError:
            return {'valid': False, 'error': 'Cannot reach Steam API'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def get_owned_games(self):
        """Fetch all owned games from Steam."""
        try:
            resp = requests.get(
                f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v1/",
                params={
                    'key': self.api_key,
                    'steamid': self.steam_id,
                    'include_appinfo': 'true',
                    'include_played_free_games': 'true',
                    'format': 'json',
                },
                timeout=30,
            )

            if resp.status_code == 403:
                logger.error("Steam API key invalid or revoked")
                return []
            if resp.status_code != 200:
                logger.error(f"Steam API error: {resp.status_code}")
                return []

            data = resp.json()
            games_data = data.get('response', {}).get('games', [])
            logger.info(f"Steam account: {len(games_data)} owned games")

            games = []
            for g in games_data:
                appid = str(g.get('appid', ''))
                name = g.get('name', f'App {appid}')
                playtime_minutes = g.get('playtime_forever', 0)
                last_played = g.get('rtime_last_played', 0)

                # Steam artwork URLs (public CDN, no auth needed)
                artwork = {
                    'header': f'{STEAM_CDN}/{appid}/header.jpg',
                    'cover': f'{STEAM_CDN}/{appid}/library_600x900_2x.jpg',
                    'hero': f'{STEAM_CDN}/{appid}/library_hero.jpg',
                    'logo': f'{STEAM_CDN}/{appid}/logo.png',
                }

                games.append({
                    'id': f'steam_{appid}',
                    'name': name,
                    'source': 'steam',
                    'appid': appid,
                    'installed': False,  # Will be merged with local scan
                    'size': 0,
                    'artwork': artwork,
                    'launch_cmd': f'steam://run/{appid}',
                    'playtime_from_api': round(playtime_minutes / 60, 1),
                    'last_played_from_api': last_played if last_played > 0 else None,
                })

            return games

        except Exception as e:
            logger.error(f"Steam API fetch failed: {e}")
            return []



def detect_steam_users() -> list[dict]:
    """Auto-detect Steam users from local loginusers.vdf.

    Returns a list of dicts with steam_id, account_name, persona_name,
    and most_recent (bool). The most recently logged-in user is first.
    """
    steam_path = _find_steam_path()
    if not steam_path:
        return []

    login_file = steam_path / 'config' / 'loginusers.vdf'
    if not login_file.exists():
        return []

    try:
        import vdf as vdf_lib
        with open(login_file, 'r', encoding='utf-8') as f:
            data = vdf_lib.load(f)

        users_data = data.get('users', {})
        users = []
        for steam_id, info in users_data.items():
            users.append({
                'steam_id': steam_id,
                'account_name': info.get('AccountName', ''),
                'persona_name': info.get('PersonaName', ''),
                'most_recent': info.get('MostRecent', '0') == '1',
            })

        # Sort so most recent user is first
        users.sort(key=lambda u: not u['most_recent'])
        return users
    except Exception as e:
        logger.debug(f"Failed to parse loginusers.vdf: {e}")
        return []


def _find_steam_path() -> Path | None:
    """Find Steam installation path from registry or common locations."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        return Path(steam_path)
    except Exception:
        for p in [Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam")]:
            if p.exists():
                return p
    return None


def resolve_steam_vanity_url(api_key, vanity_name):
    """Resolve a Steam vanity URL name to a Steam ID.
    e.g. 'gabelogannewell' → '76561197960287930'
    """
    try:
        resp = requests.get(
            f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v1/",
            params={'key': api_key, 'vanityurl': vanity_name},
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        result = data.get('response', {})
        if result.get('success') == 1:
            return result.get('steamid')
        return None
    except Exception as e:
        logger.debug(f"Failed to resolve Steam vanity URL '{vanity_name}': {e}")
        return None


# ── GOG Galaxy 2.0 Database ─────────────────────────────────────────────────

class GogGalaxyDB:
    """Read games from GOG Galaxy 2.0's local SQLite database.

    Schema (actual tables):
      - LibraryReleases: user's owned games (releaseKey = 'platform_id')
      - GamePieces: metadata per game (title, images, etc.)
      - GamePieceTypes: maps type IDs to names (157=title, 80=originalTitle, 77=originalImages)
      - PlatformConnections: which platforms user has connected
    """

    DB_PATH = Path("C:/ProgramData/GOG.com/Galaxy/storage/galaxy-2.0.db")

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else self.DB_PATH

    def is_available(self):
        return self.db_path.exists()

    def get_connected_platforms(self):
        """Get platforms from the library (based on actual owned games)."""
        if not self.is_available():
            return []

        platforms = set()
        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT substr(releaseKey, 1, instr(releaseKey, '_') - 1)
                    FROM LibraryReleases
                    WHERE releaseKey LIKE '%_%'
                """)
                for (p,) in cursor.fetchall():
                    if p:
                        platforms.add(p)
        except Exception as e:
            logger.warning(f"GOG Galaxy DB read failed: {e}")

        return sorted(platforms)

    def get_all_games(self):
        """Fetch all owned games from the Galaxy database."""
        if not self.is_available():
            logger.info("GOG Galaxy database not found")
            return []

        games = []
        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                cursor = conn.cursor()

                # Get type IDs we care about
                # 157 = title, 80 = originalTitle, 77 = originalImages, 76 = media
                type_map = {}
                cursor.execute("SELECT id, type FROM GamePieceTypes")
                for tid, ttype in cursor.fetchall():
                    type_map[tid] = ttype

                title_ids = [tid for tid, t in type_map.items() if t in ('title', 'originalTitle')]
                image_ids = [tid for tid, t in type_map.items() if t in ('originalImages', 'media')]

                # Get all owned release keys
                cursor.execute("SELECT DISTINCT releaseKey FROM LibraryReleases")
                release_keys = [r[0] for r in cursor.fetchall()]

                # Fetch titles
                titles = {}
                if title_ids:
                    ph = ','.join('?' * len(title_ids))
                    cursor.execute(f"""
                        SELECT releaseKey, gamePieceTypeId, value
                        FROM GamePieces
                        WHERE gamePieceTypeId IN ({ph})
                    """, title_ids)
                    for rk, tid, val in cursor.fetchall():
                        try:
                            data = json.loads(val)
                            title = data.get('title', '') if isinstance(data, dict) else str(data)
                            if title and rk not in titles:
                                titles[rk] = title
                        except (json.JSONDecodeError, TypeError):
                            pass

                # Fetch images
                images = {}
                if image_ids:
                    ph = ','.join('?' * len(image_ids))
                    cursor.execute(f"""
                        SELECT releaseKey, value
                        FROM GamePieces
                        WHERE gamePieceTypeId IN ({ph})
                    """, image_ids)
                    for rk, val in cursor.fetchall():
                        if rk in images:
                            continue
                        try:
                            data = json.loads(val)
                            if isinstance(data, dict):
                                # Try various image keys Galaxy uses
                                url = (data.get('verticalCover', '') or
                                       data.get('background', '') or
                                       data.get('squareIcon', ''))
                                if url:
                                    images[rk] = url
                            elif isinstance(data, str) and data.startswith('http'):
                                images[rk] = data
                        except (json.JSONDecodeError, TypeError):
                            pass

            # Build game list
            seen = set()
            for key in release_keys:
                if '_' not in key:
                    continue

                platform = key.split('_')[0]
                game_id_raw = '_'.join(key.split('_')[1:])

                title = titles.get(key, '')
                if not title:
                    continue  # Skip games with no title

                # Skip duplicate Amazon Prime entries
                # (Galaxy often has both "Game" and "Game - Amazon Prime")
                base_title = title.replace(' - Amazon Prime', '').strip()
                dedup_key = f"{platform}:{base_title.lower()}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Use cleaned title (prefer non-Amazon-Prime version)
                display_title = base_title

                artwork = {}
                img = images.get(key, '')
                if img:
                    artwork['cover'] = img

                launch_cmd = ''
                if platform == 'gog':
                    launch_cmd = f'goggalaxy://openGameView/{game_id_raw}'

                games.append({
                    'id': f'gog_{game_id_raw}',
                    'name': display_title,
                    'source': 'gog',
                    'platform_name': 'GOG',
                    'galaxy_key': key,
                    'installed': False,
                    'size': 0,
                    'artwork': artwork,
                    'launch_cmd': launch_cmd,
                })

            logger.info(f"GOG Galaxy DB: {len(games)} games")

        except Exception as e:
            logger.error(f"GOG Galaxy DB read failed: {e}")

        return games


# ── Epic Games (local catalog cache) ───────────────────────────────────────

class EpicCatalogDB:
    """Read owned games from Epic Games Launcher's local catalog cache.

    Epic stores the user's owned library in a base64-encoded JSON file:
      ProgramData/Epic/EpicGamesLauncher/Data/Catalog/catcache.bin

    This works automatically when Epic Launcher is installed and the user
    has logged in at least once — no third-party tools needed.
    """

    LAUNCHER_DIR = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / \
                   "Epic" / "EpicGamesLauncher"
    CATALOG_PATH = LAUNCHER_DIR / "Data" / "Catalog" / "catcache.bin"

    def __init__(self, catalog_path: Path | None = None):
        self.catalog_path = Path(catalog_path) if catalog_path else self.CATALOG_PATH

    def is_launcher_installed(self) -> bool:
        """Check if Epic Games Launcher directory exists."""
        return self.LAUNCHER_DIR.exists()

    def is_available(self) -> bool:
        """Check if the catalog cache exists (user has logged in)."""
        return self.catalog_path.exists()

    def get_all_games(self) -> list[dict]:
        """Fetch all owned games from the Epic catalog cache."""
        if not self.is_available():
            logger.info("Epic catalog cache not found")
            return []

        try:
            with open(self.catalog_path, 'rb') as f:
                raw = f.read()

            decoded = base64.b64decode(raw)
            catalog = json.loads(decoded)
        except (base64.binascii.Error, json.JSONDecodeError) as e:
            logger.error(f"Epic catalog cache decode failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Epic catalog cache read failed: {e}")
            return []

        games = []
        seen = set()

        for item in catalog:
            # Filter to actual games (skip DLC, engines, tools, etc.)
            categories = item.get('categories', [])
            cat_paths = [c.get('path', '') for c in categories]
            if 'games' not in cat_paths and 'games/edition' not in cat_paths:
                continue

            title = item.get('title', '')
            namespace = item.get('namespace', '')
            if not title:
                continue

            # Get app ID from releaseInfo
            release_info = item.get('releaseInfo', [])
            app_name = release_info[0].get('appId', '') if release_info else ''
            if not app_name:
                app_name = item.get('entitlementName', '')

            # Deduplicate (e.g. beta/test versions of same game)
            dedup_key = title.lower().strip()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Extract artwork from keyImages
            artwork = {}
            for img in item.get('keyImages', []):
                img_type = img.get('type', '')
                img_url = img.get('url', '')
                if img_type == 'DieselGameBoxTall' and img_url:
                    artwork['cover'] = img_url
                elif img_type == 'DieselGameBox' and img_url:
                    artwork['header'] = img_url
                elif img_type == 'DieselGameBoxLogo' and img_url:
                    artwork['logo'] = img_url

            games.append({
                'id': f'epic_{app_name}',
                'name': title,
                'source': 'epic',
                'app_name': app_name,
                'namespace': namespace,
                'installed': False,  # Will be merged with local scan
                'size': 0,
                'artwork': artwork,
                'launch_cmd': f'com.epicgames.launcher://apps/{namespace}?action=launch&silent=true' if namespace else '',
            })

        logger.info(f"Epic catalog: {len(games)} owned games")
        return games


# ── Epic Games (via legendary — optional) ──────────────────────────────────

class EpicAccount:
    """Fetch Epic Games library using the 'legendary' CLI tool.

    legendary is an open-source Epic Games client:
      pip install legendary-gl
      legendary auth  (opens browser for Epic login)
      legendary list  (shows all owned games)

    Game data is cached locally after first auth.
    """

    @staticmethod
    def is_available():
        """Check if legendary is installed."""
        import shutil
        return shutil.which('legendary') is not None

    @staticmethod
    def is_authenticated():
        """Check if legendary has a valid auth session."""
        if not EpicAccount.is_available():
            return False
        try:
            import subprocess
            result = subprocess.run(
                ['legendary', 'status', '--json'],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get('account', '') != ''
        except Exception:
            pass

        # Fallback: check if user.json exists
        user_json = Path.home() / '.config' / 'legendary' / 'user.json'
        if not user_json.exists():
            user_json = Path(os.environ.get('USERPROFILE', '')) / '.config' / 'legendary' / 'user.json'
        return user_json.exists()

    @staticmethod
    def get_owned_games():
        """Fetch all owned Epic games via legendary."""
        if not EpicAccount.is_available():
            logger.info("legendary not installed — Epic account not available")
            return []

        try:
            import subprocess
            result = subprocess.run(
                ['legendary', 'list', '--json'],
                capture_output=True, text=True, timeout=60,
            )

            if result.returncode != 0:
                logger.warning(f"legendary list failed: {result.stderr[:200]}")
                return []

            games_data = json.loads(result.stdout)
            games = []

            for g in games_data:
                app_name = g.get('app_name', '')
                title = g.get('app_title', g.get('title', app_name))
                namespace = g.get('namespace', '')

                if not title or not app_name:
                    continue

                # Skip DLC, engines, etc.
                categories = g.get('metadata', {}).get('categories', [])
                cat_names = [c.get('path', '') for c in categories]
                if 'dlc' in cat_names or 'engines' in cat_names:
                    continue

                # Artwork
                artwork = {}
                key_images = g.get('metadata', {}).get('keyImages', [])
                for img in key_images:
                    img_type = img.get('type', '')
                    img_url = img.get('url', '')
                    if img_type == 'DieselGameBoxTall' and img_url:
                        artwork['cover'] = img_url
                    elif img_type == 'DieselGameBox' and img_url:
                        artwork['header'] = img_url
                    elif img_type == 'DieselGameBoxLogo' and img_url:
                        artwork['logo'] = img_url

                # Check if installed
                install_path = g.get('install_path', '')
                installed = bool(install_path and Path(install_path).exists())

                games.append({
                    'id': f'epic_{app_name}',
                    'name': title,
                    'source': 'epic',
                    'app_name': app_name,
                    'namespace': namespace,
                    'installed': installed,
                    'install_dir': install_path,
                    'size': 0,
                    'artwork': artwork,
                    'launch_cmd': f'com.epicgames.launcher://apps/{namespace}?action=launch&silent=true' if namespace else '',
                })

            logger.info(f"Epic (legendary): {len(games)} owned games")
            return games

        except json.JSONDecodeError:
            # legendary might not output JSON in older versions
            logger.warning("legendary output is not JSON — try updating: pip install -U legendary-gl")
            return []
        except Exception as e:
            logger.error(f"Epic game fetch failed: {e}")
            return []

    @staticmethod
    def start_auth():
        """Start the legendary auth flow (opens browser)."""
        if not EpicAccount.is_available():
            return {'status': 'error', 'message': 'legendary not installed. Run: pip install legendary-gl'}

        try:
            import subprocess
            # This opens a browser for Epic login
            result = subprocess.run(
                ['legendary', 'auth'],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return {'status': 'ok', 'message': 'Epic account connected!'}
            else:
                return {'status': 'error', 'message': result.stderr[:200]}
        except subprocess.TimeoutExpired:
            return {'status': 'error', 'message': 'Auth timed out — try again'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
