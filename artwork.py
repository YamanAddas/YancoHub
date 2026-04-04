"""
YancoHub Artwork Scraper — Auto-fetches and caches game cover art.

Priority chain:
  1. Local file (Steam appcache for Steam games)
  2. Cache (already downloaded)
  3. Steam CDN (for Steam games)
  4. LibRetro thumbnails CDN (for retro games)
  5. SteamGridDB API (for PC games)
  6. Fallback (hex card with system colors)
"""

import os
import re
import logging
import requests
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger('yancohub.artwork')

CACHE_DIR = Path(__file__).parent / 'cache' / 'artwork'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

STEAM_CDN = 'https://cdn.cloudflare.steamstatic.com/steam/apps'
LIBRETRO_THUMB = 'https://thumbnails.libretro.com'

# LibRetro system directory names
LIBRETRO_SYSTEMS = {
    'nes':          'Nintendo - Nintendo Entertainment System',
    'snes':         'Nintendo - Super Nintendo Entertainment System',
    'gb':           'Nintendo - Game Boy',
    'gbc':          'Nintendo - Game Boy Color',
    'gba':          'Nintendo - Game Boy Advance',
    'n64':          'Nintendo - Nintendo 64',
    'nds':          'Nintendo - Nintendo DS',
    'megadrive':    'Sega - Mega Drive - Genesis',
    'mastersystem': 'Sega - Master System - Mark III',
    'gamegear':     'Sega - Game Gear',
    'atari2600':    'Atari - 2600',
    'psx':          'Sony - PlayStation',
    'ps2':          'Sony - PlayStation 2',
    'psp':          'Sony - PlayStation Portable',
    'dreamcast':    'Sega - Dreamcast',
    'saturn':       'Sega - Saturn',
    'gamecube':     'Nintendo - GameCube',
    'wii':          'Nintendo - Wii',
    'neogeo':       'SNK - Neo Geo',
    'ngp':          'SNK - Neo Geo Pocket',
    'fbneo':        'FBNeo - Arcade Games',
    'cps1':         'FBNeo - Arcade Games',
    'cps2':         'FBNeo - Arcade Games',
    'cps3':         'FBNeo - Arcade Games',
    'mame':         'MAME',
}


class ArtworkScraper:
    """Fetches and caches game artwork from multiple free sources."""

    def __init__(self, steamgriddb_api_key=''):
        self._session = requests.Session()
        self._session.headers['User-Agent'] = 'YancoHub/1.0'
        self._sgdb_key = steamgriddb_api_key

    def get_artwork_path(self, game, art_type='cover'):
        """Get artwork for a game. Returns local file path or None.

        Checks cache first, then fetches from appropriate source.
        """
        game_id = game.get('id', '')
        if not game_id:
            return None

        # 1. Check cache
        cached = self._get_cached(game_id, art_type)
        if cached:
            return cached

        # 2. Check local Steam artwork
        if game.get('source') == 'steam' and game.get('appid'):
            local = self._find_local_steam_art(game['appid'], art_type)
            if local:
                return local

        # 3. Try to download
        url = self._resolve_artwork_url(game, art_type)
        if url:
            downloaded = self._download_and_cache(game_id, art_type, url)
            if downloaded:
                return downloaded

        return None

    def get_artwork_url(self, game, art_type='cover'):
        """Get a remote artwork URL without downloading."""
        return self._resolve_artwork_url(game, art_type)

    def _get_cached(self, game_id, art_type):
        """Check if artwork is already cached locally."""
        for ext in ('.jpg', '.png', '.webp'):
            path = CACHE_DIR / f"{game_id}_{art_type}{ext}"
            if path.exists():
                return str(path)
        return None

    def _find_local_steam_art(self, appid, art_type):
        """Check Steam's local artwork cache."""
        # Find Steam installation
        steam_paths = []
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
            winreg.CloseKey(key)
            steam_paths.append(Path(steam_path))
        except Exception:
            pass

        steam_paths.extend([
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
        ])

        art_map = {
            'cover': [f'{appid}_library_600x900.jpg', f'{appid}_library_600x900_2x.jpg'],
            'header': [f'{appid}_header.jpg'],
            'hero': [f'{appid}_library_hero.jpg'],
            'logo': [f'{appid}_logo.png'],
        }

        patterns = art_map.get(art_type, [])

        for steam_dir in steam_paths:
            cache_dir = steam_dir / 'appcache' / 'librarycache'
            if not cache_dir.exists():
                continue
            for pattern in patterns:
                art_path = cache_dir / pattern
                if art_path.exists():
                    return str(art_path)

        return None

    def _resolve_artwork_url(self, game, art_type):
        """Determine the best remote URL for artwork."""
        source = game.get('source', '')
        system = game.get('system', '')
        game_name = game.get('name', '')

        # Steam CDN
        if source == 'steam' and game.get('appid'):
            appid = game['appid']
            urls = {
                'cover': f'{STEAM_CDN}/{appid}/library_600x900_2x.jpg',
                'header': f'{STEAM_CDN}/{appid}/header.jpg',
                'hero': f'{STEAM_CDN}/{appid}/library_hero.jpg',
                'logo': f'{STEAM_CDN}/{appid}/logo.png',
            }
            return urls.get(art_type)

        # LibRetro thumbnails (retro games)
        if source == 'retro' and system in LIBRETRO_SYSTEMS:
            libretro_system = LIBRETRO_SYSTEMS[system]
            # LibRetro uses the ROM filename stem, cleaned
            clean_name = self._clean_libretro_name(game_name)
            art_type_map = {
                'cover': 'Named_Boxarts',
                'header': 'Named_Titles',
                'screenshot': 'Named_Snaps',
            }
            lt_type = art_type_map.get(art_type, 'Named_Boxarts')
            url = f'{LIBRETRO_THUMB}/{quote(libretro_system)}/{lt_type}/{quote(clean_name)}.png'
            return url

        # SteamGridDB (PC games from other stores)
        if self._sgdb_key and source in ('epic', 'gog', 'ea', 'ubisoft', 'battlenet', 'local'):
            return self._steamgriddb_search(game_name, art_type)

        return None

    def _clean_libretro_name(self, name):
        """Clean a game name for LibRetro thumbnail lookup.
        LibRetro uses specific naming: no special chars, ampersand as &, etc.
        """
        # Remove region tags
        clean = re.sub(r'\s*[\(\[].*?[\)\]]', '', name).strip()
        # Replace characters that LibRetro doesn't use in filenames
        clean = clean.replace('/', '_')
        clean = clean.replace('\\', '_')
        clean = clean.replace(':', ' -')
        clean = clean.replace('?', '')
        clean = clean.replace('"', "'")
        clean = clean.replace('*', '_')
        clean = clean.replace('<', '_')
        clean = clean.replace('>', '_')
        clean = clean.replace('|', '_')
        return clean

    def _steamgriddb_search(self, game_name, art_type):
        """Search SteamGridDB for artwork."""
        if not self._sgdb_key:
            return None

        try:
            # Search for game
            resp = self._session.get(
                f'https://www.steamgriddb.com/api/v2/search/autocomplete/{quote(game_name)}',
                headers={'Authorization': f'Bearer {self._sgdb_key}'},
                timeout=8,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            games = data.get('data', [])
            if not games:
                return None

            game_id = games[0].get('id')

            # Get artwork
            art_endpoint = {
                'cover': f'grids/game/{game_id}?dimensions=600x900',
                'header': f'grids/game/{game_id}?dimensions=920x430',
                'hero': f'heroes/game/{game_id}',
                'logo': f'logos/game/{game_id}',
            }
            endpoint = art_endpoint.get(art_type, art_endpoint['cover'])

            resp = self._session.get(
                f'https://www.steamgriddb.com/api/v2/{endpoint}',
                headers={'Authorization': f'Bearer {self._sgdb_key}'},
                timeout=8,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            results = data.get('data', [])
            if results:
                return results[0].get('url')

        except Exception as e:
            logger.debug(f"SteamGridDB search failed for {game_name}: {e}")

        return None

    def _download_and_cache(self, game_id, art_type, url):
        """Download artwork from URL and save to cache."""
        try:
            resp = self._session.get(url, timeout=15, stream=True)
            if resp.status_code != 200:
                return None

            # Determine extension from content type or URL
            content_type = resp.headers.get('content-type', '')
            if 'png' in content_type or url.endswith('.png'):
                ext = '.png'
            elif 'webp' in content_type or url.endswith('.webp'):
                ext = '.webp'
            else:
                ext = '.jpg'

            cache_path = CACHE_DIR / f"{game_id}_{art_type}{ext}"

            with open(cache_path, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

            # Verify file isn't empty or too small (probably an error page)
            if cache_path.stat().st_size < 1000:
                cache_path.unlink()
                return None

            return str(cache_path)

        except Exception as e:
            logger.debug(f"Artwork download failed for {game_id}: {e}")
            return None

    def fetch_for_games(self, games, art_type='cover', batch_delay=0.1):
        """Batch fetch artwork for a list of games."""
        fetched = 0
        skipped = 0

        for game in games:
            game_id = game.get('id', '')
            if not game_id:
                continue

            # Skip if already cached
            if self._get_cached(game_id, art_type):
                skipped += 1
                continue

            path = self.get_artwork_path(game, art_type)
            if path:
                fetched += 1

            if batch_delay:
                import time
                time.sleep(batch_delay)

        logger.info(f"Artwork: fetched {fetched}, skipped {skipped} (already cached)")
        return fetched
