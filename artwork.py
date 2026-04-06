"""
YancoHub Artwork Scraper — Auto-fetches and caches game cover art.

Priority chain:
  1. Cache (already downloaded)
  2. LaunchBox Images folder (if configured — served directly, no copy)
  3. Local file (Steam appcache for Steam games)
  4. Steam CDN (for Steam games)
  5. LibRetro thumbnails CDN (for retro games)
  6. SteamGridDB API (for PC games)
  7. Fallback (hex card with system colors)
"""


import re
import time
import json
import logging
import threading
import concurrent.futures
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from constants import LIBRETRO_SYSTEMS, STEAM_CDN, LIBRETRO_THUMB, VERSION
from romident import read_rom_header_name, fuzzy_match, strip_numbering

logger = logging.getLogger('yancohub.artwork')

CACHE_DIR = Path(__file__).parent / 'cache' / 'artwork'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Negative cache: don't re-attempt failed artwork lookups within this window
MISS_TTL = 86400  # 24 hours


# YancoHub system ID → LaunchBox platform folder name
_LB_PLATFORMS = {
    'snes':         'Super Nintendo Entertainment System',
    'nes':          'Nintendo Entertainment System',
    'gba':          'Nintendo Game Boy Advance',
    'gb':           'Nintendo Game Boy',
    'gbc':          'Nintendo Game Boy Color',
    'n64':          'Nintendo 64',
    'nds':          'Nintendo DS',
    'megadrive':    'Sega Genesis',
    'mastersystem': 'Sega Master System',
    'gamegear':     'Sega Game Gear',
    'atari2600':    'Atari 2600',
    'atari7800':    'Atari 7800',
    'psx':          'Sony Playstation',
    'ps2':          'Sony Playstation 2',
    'psp':          'Sony PSP',
    'dreamcast':    'Sega Dreamcast',
    'gamecube':     'Nintendo GameCube',
    'neogeo':       'SNK Neo Geo CD',
    'fbneo':        'fbneo',
    'cps1':         'fbneo',
    'cps2':         'fbneo',
    'cps3':         'fbneo',
    'saturn':       'Sega Saturn',
    'wii':          'Nintendo Wii',
    'mame':         'Arcade',
    'ngp':          'SNK Neo Geo Pocket',
    'atari5200':    'Atari 5200',
    'atari7800':    'Atari 7800',
    'atarilynx':    'Atari Lynx',
    'atarist':      'Atari ST',
    'atarijaguar':  'Atari Jaguar',
    'colecovision': 'ColecoVision',
    'c64':          'Commodore 64',
    'amiga':        'Commodore Amiga',
    'dos':          'MS-DOS',
    'pcengine':     'NEC TurboGrafx-16',
    'famicom':      'Nintendo Entertainment System',
    'fds':          'Nintendo Famicom Disk System',
    'channelf':     'Fairchild Channel F',
    'arcade':       'Arcade',
    'atomiswave':   'Sammy Atomiswave',
    'daphne':       'American Laser Games',
    'gameandwatch': 'Nintendo Game & Watch',
    'odyssey2':     'Magnavox Odyssey 2',
    'vectrex':      'GCE Vectrex',
    'wonderswan':   'Bandai WonderSwan',
    'wonderswanc':  'Bandai WonderSwan Color',
    'intellivision':'Mattel Intellivision',
    '3do':          '3DO Interactive Multiplayer',
}

# YancoHub art type → LaunchBox subfolder names (tried in order)
_LB_ART_FOLDERS_RETRO = {
    'cover':      ['Box - Front', 'Box - Front - Reconstructed', 'Poster'],
    'header':     ['Banner', 'Arcade - Marquee'],
    'hero':       ['Fanart - Background', 'Fanart - Box - Front'],
    'logo':       ['Clear Logo'],
    'screenshot': ['Screenshot - Gameplay', 'Screenshot - Game Title', 'Screenshot - Game Over'],
}

_LB_ART_FOLDERS_PC = {
    'cover':      ['Steam Poster', 'Box - Front', 'Box - Front - Reconstructed',
                   'GOG Poster', 'Epic Games Poster', 'Poster'],
    'header':     ['Steam Banner', 'Banner'],
    'hero':       ['Fanart - Background', 'Fanart - Box - Front'],
    'logo':       ['Clear Logo'],
    'screenshot': ['Screenshot - Gameplay', 'Steam Screenshot',
                   'Screenshot - Game Title', 'GOG Screenshot',
                   'Amazon Screenshot'],
}


def _strip_num_prefix(name: str) -> str:
    """Remove leading number prefixes like '001 ', '000 ' from ROM names."""
    return re.sub(r'^\d{2,4}[\s._-]+', '', name)


class ArtworkScraper:
    """Fetches and caches game artwork from multiple free sources."""

    def __init__(self, steamgriddb_api_key='', launchbox_path=''):
        self._session = requests.Session()
        self._session.headers['User-Agent'] = f'YancoHub/{VERSION}'
        retry = Retry(total=3, backoff_factor=1.0,
                      status_forcelist=[429, 500, 502, 503, 504])
        self._session.mount('https://', HTTPAdapter(max_retries=retry))
        self._session.mount('http://', HTTPAdapter(max_retries=retry))
        self._sgdb_key = steamgriddb_api_key
        self._lb_path = self._resolve_lb_root(launchbox_path)
        # ROM filename → LaunchBox title index (built from platform XMLs)
        self._lb_title_index: dict[str, str] = {}
        # Artwork filename index: per platform, normalized_name → actual_art_filename
        # Built from scanning the actual Images/ folder (the real authority)
        self._lb_art_index: dict[str, dict[str, str]] = {}  # {platform: {norm_name: filename}}
        # Resolved title cache: game_id → LaunchBox title (avoids re-reading headers)
        self._resolved_cache: dict[str, str] = {}
        # Artwork match cache: (game_id, art_type) → resolved art filename or None
        self._art_match_cache: dict[tuple[str, str], str | None] = {}
        if self._lb_path:
            self._build_lb_title_index()
            self._build_lb_art_index()
        # Steam bulk app list for instant local name→appid lookups
        self._steam_app_list: dict[str, str] = {}  # normalized name → appid
        self._steam_app_list_loaded = False
        # Lock for concurrent batch fetching
        self._fetch_lock = threading.Lock()
        # Batch fetch progress tracking
        self.batch_progress = {'active': False, 'fetched': 0, 'total': 0, 'done': False}

    def get_artwork_path(self, game, art_type='cover'):
        """Get artwork for a game. Returns local file path or None.

        Checks cache first, then fetches from appropriate source.
        Failed lookups are negative-cached for 24h to avoid repeated attempts.
        """
        game_id = game.get('id', '')
        if not game_id:
            return None

        # 1. Check cache
        cached = self._get_cached(game_id, art_type)
        if cached:
            return cached

        # 1b. Skip known failures (negative cache)
        if self._is_negative_cached(game_id, art_type):
            return None

        # 2. Check LaunchBox artwork (serves directly, no copy)
        lb_art = self._find_launchbox_art(game, art_type)
        if lb_art:
            return lb_art

        # 3. Check local Steam artwork
        if game.get('source') == 'steam' and game.get('appid'):
            local = self._find_local_steam_art(game['appid'], art_type)
            if local:
                return local

        # 3b. Check UWP/MS Store app assets
        if game.get('source') == 'xbox' and game.get('install_dir'):
            local = self._find_uwp_art(game['install_dir'], art_type)
            if local:
                return local

        # 4. Try to download (with name variants for retro games)
        source = game.get('source', '')
        system = game.get('system', '')
        if source == 'retro' and system in LIBRETRO_SYSTEMS:
            downloaded = self._try_libretro_variants(game, art_type)
        else:
            url = self._resolve_artwork_url(game, art_type)
            downloaded = self._download_and_cache(game_id, art_type, url) if url else None

        if downloaded:
            return downloaded

        # 5. All sources exhausted — mark as miss to avoid re-attempting
        self._mark_miss(game_id, art_type)
        return None

    def get_artwork_path_cached_only(self, game, art_type='cover'):
        """Fast path: return artwork only from cache and local sources (no network).

        Used by the HTTP endpoint to avoid blocking on slow network lookups.
        """
        game_id = game.get('id', '')
        if not game_id:
            return None

        cached = self._get_cached(game_id, art_type)
        if cached:
            return cached

        lb_art = self._find_launchbox_art(game, art_type)
        if lb_art:
            return lb_art

        if game.get('source') == 'steam' and game.get('appid'):
            local = self._find_local_steam_art(game['appid'], art_type)
            if local:
                return local

        if game.get('source') == 'xbox' and game.get('install_dir'):
            local = self._find_uwp_art(game['install_dir'], art_type)
            if local:
                return local

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

    def _is_negative_cached(self, game_id: str, art_type: str) -> bool:
        """Check if this artwork was previously attempted and failed."""
        miss_path = CACHE_DIR / f"{game_id}_{art_type}.miss"
        if miss_path.exists():
            try:
                age = time.time() - miss_path.stat().st_mtime
                if age < MISS_TTL:
                    return True
                miss_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False

    def _mark_miss(self, game_id: str, art_type: str):
        """Record a failed artwork lookup to avoid re-attempting for 24h."""
        try:
            miss_path = CACHE_DIR / f"{game_id}_{art_type}.miss"
            miss_path.write_text('')
        except OSError:
            pass

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
            'cover': [f'{appid}/library_600x900.jpg', f'{appid}/library_600x900_2x.jpg',
                      f'{appid}_library_600x900.jpg', f'{appid}_library_600x900_2x.jpg'],
            'header': [f'{appid}/library_header.jpg', f'{appid}/header.jpg',
                       f'{appid}_header.jpg'],
            'hero': [f'{appid}/library_hero.jpg', f'{appid}_library_hero.jpg'],
            'logo': [f'{appid}/logo.png', f'{appid}_logo.png'],
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

    @staticmethod
    def _resolve_lb_root(path: str):
        """Resolve the LaunchBox root directory.

        If the user points to a subfolder like Images/ or Data/, go up to the root.
        The root is identified by containing both Images/ and Data/ subdirectories.
        """
        if not path:
            return None
        p = Path(path)
        if not p.is_dir():
            return None
        # Check if this is already the root (has Images/ and/or Data/)
        if (p / 'Images').is_dir() or (p / 'Data').is_dir():
            return p
        # Check if user pointed to a subfolder (e.g. Images, Data, Games)
        parent = p.parent
        if (parent / 'Images').is_dir() or (parent / 'Data').is_dir():
            logger.info(f"LaunchBox path adjusted from subfolder to root: {parent}")
            return parent
        # Accept as-is
        return p

    def get_platform_artwork(self, system: str) -> str | None:
        """Get console/platform artwork from LaunchBox Images/Platforms/ folder.

        Returns path to a Banner or Device image for the given system, or None.
        """
        if not self._lb_path:
            return None
        platform_name = _LB_PLATFORMS.get(system)
        if not platform_name:
            return None
        platforms_dir = self._lb_path / 'Images' / 'Platforms' / platform_name
        if not platforms_dir.is_dir():
            return None
        # Try image types in priority order
        for subfolder in ('Banner', 'Device', 'Fanart', 'Clear Logo', 'Default Box'):
            folder = platforms_dir / subfolder
            if not folder.is_dir():
                continue
            for ext in ('*.jpg', '*.png', '*.webp', '*.gif'):
                matches = list(folder.glob(ext))
                if matches:
                    return str(matches[0])
        return None

    def set_launchbox_path(self, path: str):
        """Update the LaunchBox path at runtime and rebuild all indexes."""
        self._lb_path = self._resolve_lb_root(path)
        self._lb_title_index = {}
        self._lb_art_index = {}
        self._resolved_cache = {}
        self._art_match_cache = {}
        if self._lb_path:
            self._build_lb_title_index()
            self._build_lb_art_index()

    def _build_lb_title_index(self):
        """Build a multi-strategy title index for LaunchBox artwork matching.

        Sources:
          1. Platform XMLs — maps ROM filenames → LB titles
          2. Also indexes by stripped-number variants of both ROM stems and titles
          3. Also indexes title → title (for direct title lookup)
        """
        if not self._lb_path:
            return

        data_dir = self._lb_path / 'Data' / 'Platforms'
        if not data_dir.is_dir():
            logger.debug(f"LaunchBox Data/Platforms not found at {data_dir}")
            return

        count = 0
        for xml_file in data_dir.glob('*.xml'):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                for game_el in root.findall('Game'):
                    app_path = game_el.findtext('ApplicationPath', '').strip()
                    title = game_el.findtext('Title', '').strip()
                    if not app_path or not title:
                        continue
                    rom_stem = Path(app_path).stem

                    # Primary: index by normalized ROM stem → title
                    key = self._lb_normalize(rom_stem)
                    if key:
                        self._lb_title_index[key] = title
                        count += 1

                    # Also index by number-stripped ROM stem → title
                    stripped_stem = _strip_num_prefix(rom_stem)
                    if stripped_stem != rom_stem:
                        skey = self._lb_normalize(stripped_stem)
                        if skey and skey not in self._lb_title_index:
                            self._lb_title_index[skey] = title

                    # Also index by normalized title → title
                    # (for when the game name is the proper title, not a filename)
                    tkey = self._lb_normalize(title)
                    if tkey and tkey not in self._lb_title_index:
                        self._lb_title_index[tkey] = title

            except ET.ParseError:
                logger.warning(f"Failed to parse LaunchBox XML: {xml_file.name}")
            except Exception as e:
                logger.debug(f"Error reading {xml_file.name}: {e}")

        logger.info(f"LaunchBox title index: {count} primary + "
                     f"{len(self._lb_title_index) - count} variant entries")

    def _build_lb_art_index(self):
        """Build an index of actual artwork filenames per platform.

        This is the real authority — the XML titles can be wrong (echoed filenames),
        but the artwork files always have the correct game name.
        Scans the first art subfolder (Box - Front) per platform for speed.
        """
        if not self._lb_path:
            return
        images_dir = self._lb_path / 'Images'
        if not images_dir.is_dir():
            return

        total = 0
        for platform_dir in images_dir.iterdir():
            if not platform_dir.is_dir():
                continue
            platform = platform_dir.name
            art_names = {}

            # Scan Box - Front (most complete), then Clear Logo as fallback
            for art_folder in ['Box - Front', 'Clear Logo', 'Screenshot - Gameplay']:
                art_dir = platform_dir / art_folder
                if not art_dir.is_dir():
                    continue
                # Check region subdirectories and the folder itself
                scan_dirs = [d for d in art_dir.iterdir() if d.is_dir()]
                scan_dirs.append(art_dir)
                for d in scan_dirs:
                    for f in d.iterdir():
                        if not f.is_file():
                            continue
                        stem = f.stem
                        # Strip LaunchBox suffix like "-01", "-02"
                        if re.match(r'.*-\d{2}$', stem):
                            stem = stem[:-3]
                        norm = self._lb_normalize(stem)
                        if norm and norm not in art_names:
                            art_names[norm] = stem  # Store the real filename stem
                break  # Only scan first available art folder per platform

            if art_names:
                self._lb_art_index[platform] = art_names
                total += len(art_names)

        logger.info(f"LaunchBox art index: {total} artwork entries across "
                     f"{len(self._lb_art_index)} platforms")

    def _resolve_lb_title(self, game: dict) -> str:
        """Smart multi-strategy title resolution for LaunchBox artwork matching.

        Strategies (tried in order, first match wins):
          1. Exact XML index lookup (ROM stem → LB title)
          2. Strip numbering prefix ('001 Donkey Kong' → 'Donkey Kong')
          3. ROM header name (reads internal title from binary)
          4. Fuzzy match filename against all LB titles (≥65% similarity)
          5. Fuzzy match header name against all LB titles

        Results are cached per game_id to avoid re-reading ROM headers.
        """
        game_name = game.get('name', '')
        game_id = game.get('id', '')

        if not self._lb_title_index:
            return game_name

        # Check cache first
        if game_id and game_id in self._resolved_cache:
            return self._resolved_cache[game_id]

        resolved = self._resolve_lb_title_inner(game)
        if game_id:
            self._resolved_cache[game_id] = resolved
        return resolved

    def _resolve_lb_title_inner(self, game: dict) -> str:
        game_name = game.get('name', '')
        system = game.get('system', '')
        file_path = game.get('file_path', '')

        # Strategy 1: Exact XML index lookup
        key = self._lb_normalize(game_name)
        if key in self._lb_title_index:
            return self._lb_title_index[key]

        # Strategy 2: Strip numbered prefix and retry
        stripped = strip_numbering(game_name)
        if stripped != game_name:
            key2 = self._lb_normalize(stripped)
            if key2 in self._lb_title_index:
                return self._lb_title_index[key2]

        # Strategy 3: Read ROM header for internal game name
        header_name = None
        if file_path and Path(file_path).suffix.lower() not in ('.zip', '.7z'):
            header_name = read_rom_header_name(file_path, system)
            if header_name:
                hkey = self._lb_normalize(header_name)
                if hkey in self._lb_title_index:
                    logger.debug(f"Header match: '{game_name}' → '{self._lb_title_index[hkey]}' "
                                 f"(header: {header_name})")
                    return self._lb_title_index[hkey]

        # Strategy 4-5: Fuzzy matching is done in _match_art_index against the
        # per-platform art filename index (much smaller, faster). Skip the
        # expensive full title index fuzzy scan here — it adds negligible matches
        # and costs ~100s for large libraries.
        return game_name

    def _find_launchbox_art(self, game, art_type: str):
        """Search LaunchBox Images folder for matching artwork.

        Full result caching — first call resolves, subsequent calls are instant.
        """
        if not self._lb_path:
            return None

        # Full-result cache: (game_id, art_type) → file path or None
        game_id = game.get('id', '')
        cache_key = (game_id, art_type) if game_id else None
        if cache_key and cache_key in self._art_match_cache:
            cached = self._art_match_cache[cache_key]
            if cached is None:
                return None
            if Path(cached).exists():
                return cached
            del self._art_match_cache[cache_key]

        result = self._find_launchbox_art_inner(game, art_type)
        if cache_key:
            self._art_match_cache[cache_key] = result
        return result

    def _find_launchbox_art_inner(self, game, art_type: str):
        images_dir = self._lb_path / 'Images'
        if not images_dir.is_dir():
            return None

        source = game.get('source', '')
        system = game.get('system', '')
        game_name = game.get('name', '')
        if not game_name:
            return None

        # Determine platform folder and art folder list
        if source == 'retro' and system in _LB_PLATFORMS:
            platform = _LB_PLATFORMS[system]
            art_folders = _LB_ART_FOLDERS_RETRO.get(art_type, [])
        elif source in ('steam', 'epic', 'gog', 'ea', 'ubisoft', 'battlenet', 'local', 'xbox'):
            platform = 'Windows'
            art_folders = _LB_ART_FOLDERS_PC.get(art_type, [])
        else:
            return None

        platform_dir = images_dir / platform
        if not platform_dir.is_dir():
            return None

        # Phase 1: Try XML-resolved title and original name (fast exact lookups)
        lb_title = self._resolve_lb_title(game)
        names_to_try = [lb_title]
        if lb_title != game_name:
            names_to_try.append(game_name)
        # Also try number-stripped variant
        stripped = _strip_num_prefix(game_name)
        if stripped != game_name and stripped != lb_title:
            names_to_try.append(stripped)

        for folder_name in art_folders:
            art_dir = platform_dir / folder_name
            if not art_dir.is_dir():
                continue
            for name in names_to_try:
                match = self._lb_find_file(art_dir, name)
                if match:
                    return str(match)

        # Phase 2: Use the art filename index for smart matching
        art_names = self._lb_art_index.get(platform, {})
        if not art_names:
            return None

        # Try matching against actual artwork filenames
        art_filename = self._match_art_index(game, art_names)
        if not art_filename:
            return None

        # Found an artwork filename match — now locate the actual file
        for folder_name in art_folders:
            art_dir = platform_dir / folder_name
            if not art_dir.is_dir():
                continue
            match = self._lb_find_file(art_dir, art_filename)
            if match:
                return str(match)

        return None

    def _match_art_index(self, game: dict, art_names: dict[str, str]) -> str | None:
        """Match a game against the artwork filename index.

        Tries: normalized name → stripped name → header name → fuzzy.
        Returns the actual artwork filename stem, or None.
        """
        game_name = game.get('name', '')
        system = game.get('system', '')
        file_path = game.get('file_path', '')

        # Try exact normalized match
        for name in [game_name, _strip_num_prefix(game_name)]:
            norm = self._lb_normalize(name)
            if norm in art_names:
                return art_names[norm]

        # Try ROM header name
        header_name = None
        if file_path and Path(file_path).suffix.lower() not in ('.zip', '.7z'):
            header_name = read_rom_header_name(file_path, system)
            if header_name:
                hnorm = self._lb_normalize(header_name)
                if hnorm in art_names:
                    return art_names[hnorm]

        # Fuzzy match against art filenames (smaller set than full title index)
        stripped = _strip_num_prefix(game_name)
        result = fuzzy_match(stripped, art_names, threshold=0.65)
        if result:
            return result

        if header_name:
            result = fuzzy_match(header_name, art_names, threshold=0.60)
            if result:
                return result

        return None

    @staticmethod
    def _lb_normalize(name: str) -> str:
        """Normalize a name for fuzzy LaunchBox matching."""
        n = name.lower()
        n = re.sub(r'\s*[\(\[].*?[\)\]]', '', n)   # strip region/disc tags
        n = n.replace('-', ' ').replace('_', ' ')   # treat - and _ as spaces
        n = re.sub(r'[^a-z0-9 ]', '', n)            # only alnum + space
        return ' '.join(n.split())

    def _lb_find_file(self, art_dir: Path, game_name: str):
        """Find a LaunchBox image file matching the game name.

        LaunchBox names files as "<Game Name>-01.jpg".
        Searches region subfolders (e.g. North America/) if present.
        Falls back to normalized prefix matching if exact match fails.
        """
        # Preferred region order
        regions = ['North America', 'Europe', 'Japan']

        # Check region subfolders first, then the art_dir itself
        search_dirs = []
        for region in regions:
            region_dir = art_dir / region
            if region_dir.is_dir():
                search_dirs.append(region_dir)
        search_dirs.append(art_dir)

        # Pass 1: exact name match
        for search_dir in search_dirs:
            for ext in ('.jpg', '.png', '.webp'):
                candidate = search_dir / f"{game_name}-01{ext}"
                if candidate.exists():
                    return candidate

        # Pass 2: normalized prefix scan
        norm_name = self._lb_normalize(game_name)
        if not norm_name:
            return None
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for f in search_dir.iterdir():
                if not f.is_file():
                    continue
                # Strip the "-01" suffix and extension to get the LB game name
                stem = f.stem
                if stem.endswith('-01'):
                    stem = stem[:-3]
                if self._lb_normalize(stem) == norm_name:
                    return f
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
            # Use smart-resolved title — strips numbered prefixes, reads ROM headers
            resolved = _strip_num_prefix(self._resolve_lb_title(game))
            clean_name = self._clean_libretro_name(resolved)
            art_type_map = {
                'cover': 'Named_Boxarts',
                'header': 'Named_Titles',
                'screenshot': 'Named_Snaps',
            }
            lt_type = art_type_map.get(art_type, 'Named_Boxarts')
            url = f'{LIBRETRO_THUMB}/{quote(libretro_system)}/{lt_type}/{quote(clean_name)}.png'
            return url

        # Non-Steam PC games: search Steam Store by name to find appid, then use CDN
        if source in ('epic', 'gog', 'ea', 'ubisoft', 'battlenet', 'local', 'xbox', 'amazon'):
            appid = self._search_steam_appid(game_name)
            if appid:
                urls = {
                    'cover': f'{STEAM_CDN}/{appid}/library_600x900_2x.jpg',
                    'header': f'{STEAM_CDN}/{appid}/header.jpg',
                    'hero': f'{STEAM_CDN}/{appid}/library_hero.jpg',
                    'logo': f'{STEAM_CDN}/{appid}/logo.png',
                }
                return urls.get(art_type)

        # SteamGridDB (fallback if Steam search found nothing)
        if self._sgdb_key and source in ('epic', 'gog', 'ea', 'ubisoft', 'battlenet', 'local', 'xbox', 'amazon'):
            return self._steamgriddb_search(game_name, art_type)

        return None

    def _find_uwp_art(self, install_dir: str, art_type: str) -> str | None:
        """Find artwork from UWP/Microsoft Store app assets.

        Searches the package's Assets/ folder and any subdirectories for
        icon, tile, splash, and store artwork. Also parses AppxManifest.xml
        for declared image paths. Returns the best match by type and size.
        """
        base = Path(install_dir)
        if not base.exists():
            return None

        # Pattern groups ordered by preference per art type
        # We search the entire install dir recursively (rglob)
        pattern_groups = {
            'cover': [
                '*LargeTile*', '*StoreLogo*', '*PremiumLogo*',
                '*AppList.targetsize-256*', '*AppList.targetsize-256.png',
                '*Square310x310*', '*Square150x150*',
            ],
            'header': ['*SplashScreen*', '*WideTile*', '*Wide310x150*'],
            'hero': ['*SplashScreen*', '*WideTile*', '*Wide310x150*'],
            'logo': ['*PackageLogo*', '*StoreLogo*', '*SmallTile*', '*Square44x44*'],
        }

        for pattern in pattern_groups.get(art_type, pattern_groups['cover']):
            matches = []
            for ext in ('*.png', '*.jpg', '*.jpeg'):
                for f in base.rglob(ext):
                    if f.match(pattern):
                        matches.append(f)
            if not matches:
                continue
            # Pick largest file (highest resolution), skip contrast variants
            matches.sort(key=lambda p: p.stat().st_size, reverse=True)
            for match in matches:
                name_lower = match.name.lower()
                if 'contrast-' in name_lower:
                    continue
                return str(match)

        return None

    # Cache: game name → Steam appid (avoids repeated API calls)
    _steam_appid_cache: dict[str, str | None] = {}

    def _load_steam_app_list(self):
        """Download the full Steam app list for instant local name→appid lookups.

        Replaces per-game HTTP searches with a single bulk download (~30MB).
        Cached to disk for 7 days.
        """
        if self._steam_app_list_loaded:
            return
        self._steam_app_list_loaded = True

        cache_file = CACHE_DIR.parent / 'steam_applist.json'

        # Check if cached file is fresh (< 7 days old)
        if cache_file.exists():
            try:
                age = time.time() - cache_file.stat().st_mtime
                if age < 604800:  # 7 days
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        self._steam_app_list = json.load(f)
                    logger.info(f"Steam app list loaded from cache: "
                                f"{len(self._steam_app_list)} apps")
                    return
            except Exception:
                pass

        # Download fresh list
        try:
            logger.info("Downloading Steam app list for bulk lookups...")
            resp = self._session.get(
                'https://api.steampowered.com/ISteamApps/GetAppList/v2/',
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning(f"Steam app list download failed: HTTP {resp.status_code}")
                return

            data = resp.json()
            apps = data.get('applist', {}).get('apps', [])

            # Build normalized name → appid dict (keep first/lowest appid per name)
            name_map = {}
            for app in apps:
                name = app.get('name', '').strip()
                if not name:
                    continue
                key = name.lower()
                if key not in name_map:
                    name_map[key] = str(app['appid'])

            self._steam_app_list = name_map

            # Cache to disk
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(name_map, f)

            logger.info(f"Steam app list downloaded: {len(name_map)} apps cached")
        except Exception as e:
            logger.warning(f"Failed to load Steam app list: {e}")

    # Suffixes to strip when searching for artwork (store bundles, editions)
    _NAME_STRIP_SUFFIXES = [
        ' - Amazon Prime', ' - Prime Gaming', ' - Humble Bundle',
        ' - GOG.com', ' - GOG', ' - Epic', ' (GOG)', ' (Epic)',
    ]

    def _search_steam_appid(self, game_name: str) -> str | None:
        """Search for a game's Steam appid using bulk list first, API fallback.

        Priority:
          1. In-memory cache (instant)
          2. Bulk app list — local dict lookup (instant, ~170k entries)
          3. Steam Store search API (slow, 8s timeout — last resort)
        """
        name_lower = game_name.lower().strip()
        if name_lower in self._steam_appid_cache:
            return self._steam_appid_cache[name_lower]

        # Build search name variants (original + suffix-stripped)
        search_names = [game_name]
        for suffix in self._NAME_STRIP_SUFFIXES:
            if game_name.lower().endswith(suffix.lower()):
                stripped = game_name[:len(game_name) - len(suffix)].strip()
                if stripped and stripped not in search_names:
                    search_names.append(stripped)

        # Try bulk app list first (instant local lookup)
        if self._steam_app_list:
            for sn in search_names:
                key = sn.lower().strip()
                if key in self._steam_app_list:
                    appid = self._steam_app_list[key]
                    self._steam_appid_cache[name_lower] = appid
                    return appid

        # Fall back to Steam Store search API (slow, one HTTP call per game)
        for search_name in search_names:
            try:
                resp = self._session.get(
                    'https://store.steampowered.com/api/storesearch/',
                    params={'term': search_name, 'l': 'english', 'cc': 'US'},
                    timeout=8,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                items = data.get('items', [])
                if not items:
                    continue

                # Try exact name match first, then take the first result
                search_lower = search_name.lower()
                for item in items:
                    if item.get('name', '').lower() == search_lower:
                        appid = str(item['id'])
                        self._steam_appid_cache[name_lower] = appid
                        return appid

                # First result as fallback
                appid = str(items[0]['id'])
                self._steam_appid_cache[name_lower] = appid
                return appid

            except Exception as e:
                logger.debug(f"Steam store search failed for '{search_name}': {e}")

        self._steam_appid_cache[name_lower] = None
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

    def _libretro_name_variants(self, name: str) -> list[str]:
        """Generate LibRetro-compatible name variations for thumbnail lookup.

        LibRetro uses No-Intro naming conventions which differ from common ROM
        filenames. Tries multiple transformations to improve match rate.
        """
        clean = self._clean_libretro_name(name)
        variants = [clean]

        # "Legend of Zelda, The" → "The Legend of Zelda"
        if ', The' in name:
            alt = 'The ' + name.replace(', The', '').strip()
            variants.append(self._clean_libretro_name(alt))

        # "The Legend of Zelda" → "Legend of Zelda, The"
        if name.startswith('The '):
            alt = name[4:] + ', The'
            variants.append(self._clean_libretro_name(alt))

        # Remove subtitle: "Game - Subtitle" → "Game"
        if ' - ' in clean:
            variants.append(clean.split(' - ')[0].strip())

        # Strip trailing version/revision markers
        trimmed = re.sub(r'\s*[vV]\d+(\.\d+)*\s*$', '', clean)
        if trimmed != clean:
            variants.append(trimmed)

        # Deduplicate while preserving order
        seen = set()
        return [v for v in variants if v and v not in seen and not seen.add(v)]

    def _try_libretro_variants(self, game, art_type: str):
        """Try multiple LibRetro name variations for retro artwork.

        Returns downloaded file path on first success, or None.
        """
        game_id = game.get('id', '')
        system = game.get('system', '')
        libretro_system = LIBRETRO_SYSTEMS.get(system)
        if not libretro_system:
            return None

        art_type_map = {
            'cover': 'Named_Boxarts',
            'header': 'Named_Titles',
            'screenshot': 'Named_Snaps',
        }
        lt_type = art_type_map.get(art_type, 'Named_Boxarts')

        resolved = _strip_num_prefix(self._resolve_lb_title(game))
        variants = self._libretro_name_variants(resolved)

        for name in variants:
            url = (f'{LIBRETRO_THUMB}/{quote(libretro_system)}'
                   f'/{lt_type}/{quote(name)}.png')
            result = self._download_and_cache(game_id, art_type, url)
            if result:
                return result

        # Last resort: SteamGridDB for retro games
        if self._sgdb_key:
            url = self._steamgriddb_search(game.get('name', ''), art_type)
            if url:
                return self._download_and_cache(game_id, art_type, url)

        return None

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

    def prewarm_title_cache(self, games):
        """Pre-resolve LaunchBox artwork paths for all retro games.

        Call after scan to warm all caches. Individual artwork requests then
        hit the cache instead of doing ROM header reads + fuzzy matching.
        Runs cover art resolution for every retro game in one batch.
        """
        if not self._lb_path or not self._lb_title_index:
            return
        retro = [g for g in games if g.get('source') == 'retro' and g.get('id')]
        count = 0
        for g in retro:
            # This warms both _resolved_cache and _art_match_cache
            cache_key = (g['id'], 'cover')
            if cache_key not in self._art_match_cache:
                self._find_launchbox_art(g, 'cover')
                count += 1
        logger.info(f"Pre-warmed artwork cache: {count} retro games resolved")

    def fetch_for_games(self, games, art_types=('cover',), max_workers=8,
                        timeout=600):
        """Batch fetch artwork for games using concurrent downloads.

        Args:
            games: List of game dicts to fetch artwork for.
            art_types: Tuple of art types to fetch (e.g., ('cover', 'header')).
            max_workers: Number of concurrent download threads.
            timeout: Overall time limit in seconds (default 10 minutes).
        """
        # Load Steam bulk app list before batch (one-time, ~30MB)
        if not self._steam_app_list_loaded:
            self._load_steam_app_list()

        # Build work list: (game, art_type) pairs that need fetching
        need_fetch = []
        for g in games:
            gid = g.get('id')
            if not gid:
                continue
            for at in art_types:
                if not self._get_cached(gid, at) and not self._is_negative_cached(gid, at):
                    need_fetch.append((g, at))

        total = len(need_fetch)
        self.batch_progress = {'active': True, 'fetched': 0, 'total': total, 'done': False}

        if not need_fetch:
            self.batch_progress = {'active': False, 'fetched': 0, 'total': 0, 'done': True}
            logger.info(f"Artwork batch: nothing to fetch "
                        f"({len(games) * len(art_types)} already cached/skipped)")
            return 0

        fetched = 0
        start = time.monotonic()

        def _fetch_one(item):
            nonlocal fetched
            game, art_type = item
            if (time.monotonic() - start) > timeout:
                return None
            path = self.get_artwork_path(game, art_type)
            with self._fetch_lock:
                if path:
                    fetched += 1
                self.batch_progress['fetched'] = fetched
            return path

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                list(pool.map(_fetch_one, need_fetch, timeout=timeout))
        except concurrent.futures.TimeoutError:
            logger.info(f"Artwork batch timed out after {timeout}s")
        except Exception as e:
            logger.warning(f"Artwork batch error: {e}")

        elapsed = time.monotonic() - start
        self.batch_progress = {'active': False, 'fetched': fetched, 'total': total, 'done': True}
        logger.info(f"Artwork batch complete: {fetched}/{total} fetched in {elapsed:.0f}s "
                    f"({total - fetched} failed/skipped)")
        return fetched
