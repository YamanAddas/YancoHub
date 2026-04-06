"""
YancoHub Game Library Scanner — Windows
Discovers games from Steam, Epic, GOG, Xbox/Game Pass, EA, Ubisoft, Battle.net,
local directories, and retro ROMs.
"""

import os
import re
import json
import hashlib
import logging
import sqlite3
import subprocess
from pathlib import Path

logger = logging.getLogger('yancohub.scanner')

# ── ROM system definitions ──────────────────────────────────────────────────

ROM_SYSTEMS = {
    'snes':         {'name': 'Super Nintendo',    'extensions': ['.smc', '.sfc', '.zip', '.7z'], 'core': 'snes9x_libretro.dll'},
    'nes':          {'name': 'Nintendo (NES)',     'extensions': ['.nes', '.zip', '.7z'], 'core': 'fceumm_libretro.dll'},
    'gba':          {'name': 'Game Boy Advance',   'extensions': ['.gba', '.zip', '.7z'], 'core': 'mgba_libretro.dll'},
    'gb':           {'name': 'Game Boy',           'extensions': ['.gb', '.zip', '.7z'], 'core': 'gambatte_libretro.dll'},
    'gbc':          {'name': 'Game Boy Color',     'extensions': ['.gbc', '.zip', '.7z'], 'core': 'gambatte_libretro.dll'},
    'n64':          {'name': 'Nintendo 64',        'extensions': ['.n64', '.z64', '.v64', '.zip', '.7z'], 'core': 'mupen64plus_next_libretro.dll'},
    'nds':          {'name': 'Nintendo DS',        'extensions': ['.nds', '.zip', '.7z'], 'core': 'melonds_libretro.dll'},
    'megadrive':    {'name': 'Sega Genesis',       'extensions': ['.md', '.gen', '.zip', '.7z'], 'core': 'genesis_plus_gx_libretro.dll'},
    'mastersystem': {'name': 'Sega Master System', 'extensions': ['.sms', '.zip', '.7z'], 'core': 'genesis_plus_gx_libretro.dll'},
    'gamegear':     {'name': 'Sega Game Gear',     'extensions': ['.gg', '.zip', '.7z'], 'core': 'genesis_plus_gx_libretro.dll'},
    'atari2600':    {'name': 'Atari 2600',         'extensions': ['.a26', '.bin', '.zip', '.7z'], 'core': 'stella_libretro.dll'},
    'psx':          {'name': 'PlayStation',         'extensions': ['.chd', '.bin', '.cue', '.iso', '.pbp', '.zip', '.7z'], 'core': 'swanstation_libretro.dll'},
    'ps2':          {'name': 'PlayStation 2',       'extensions': ['.chd', '.iso', '.bin', '.cue', '.7z'], 'emulator': 'pcsx2', 'core': 'pcsx2_libretro.dll'},
    'ps3':          {'name': 'PlayStation 3',       'extensions': ['.bin'], 'emulator': 'rpcs3'},  # EBOOT.BIN
    'psp':          {'name': 'PlayStation Portable','extensions': ['.iso', '.cso', '.pbp', '.7z'], 'emulator': 'ppsspp', 'core': 'ppsspp_libretro.dll'},
    'dreamcast':    {'name': 'Sega Dreamcast',     'extensions': ['.chd', '.cdi', '.gdi', '.bin', '.zip', '.7z'], 'core': 'flycast_libretro.dll'},
    'saturn':       {'name': 'Sega Saturn',        'extensions': ['.chd', '.bin', '.cue', '.iso', '.7z'], 'core': 'mednafen_saturn_libretro.dll'},
    'gamecube':     {'name': 'GameCube',           'extensions': ['.iso', '.gcm', '.rvz', '.nkit.iso', '.7z'], 'emulator': 'dolphin', 'core': 'dolphin_libretro.dll'},
    'wii':          {'name': 'Nintendo Wii',       'extensions': ['.iso', '.wbfs', '.rvz', '.wad', '.nkit.iso', '.7z'], 'emulator': 'dolphin', 'core': 'dolphin_libretro.dll'},
    'neogeo':       {'name': 'Neo Geo',            'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'fbneo':        {'name': 'FinalBurn Neo',      'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'cps1':         {'name': 'CPS-1',              'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'cps2':         {'name': 'CPS-2',              'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'cps3':         {'name': 'CPS-3',              'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'mame':         {'name': 'MAME',               'extensions': ['.zip', '.7z'], 'core': 'mame_libretro.dll'},
    'ngp':          {'name': 'Neo Geo Pocket',     'extensions': ['.ngp', '.ngc', '.zip', '.7z'], 'core': 'mednafen_ngp_libretro.dll'},
    # ── Additional platforms ──
    'atari5200':    {'name': 'Atari 5200',         'extensions': ['.a52', '.bin', '.zip', '.7z'], 'core': 'atari800_libretro.dll'},
    'atari7800':    {'name': 'Atari 7800',         'extensions': ['.a78', '.bin', '.zip', '.7z'], 'core': 'prosystem_libretro.dll'},
    'atarilynx':    {'name': 'Atari Lynx',         'extensions': ['.lnx', '.zip', '.7z'], 'core': 'handy_libretro.dll'},
    'atarist':      {'name': 'Atari ST',           'extensions': ['.st', '.stx', '.msa', '.zip', '.7z'], 'core': 'hatari_libretro.dll'},
    'atarijaguar':  {'name': 'Atari Jaguar',       'extensions': ['.j64', '.jag', '.zip', '.7z'], 'core': 'virtualjaguar_libretro.dll'},
    'colecovision': {'name': 'ColecoVision',       'extensions': ['.col', '.rom', '.bin', '.zip', '.7z'], 'core': 'bluemsx_libretro.dll'},
    'c64':          {'name': 'Commodore 64',       'extensions': ['.d64', '.t64', '.prg', '.crt', '.tap', '.zip', '.7z'], 'core': 'vice_x64_libretro.dll'},
    'amiga':        {'name': 'Amiga',              'extensions': ['.adf', '.adz', '.ipf', '.hdf', '.lha', '.zip', '.7z'], 'core': 'puae_libretro.dll'},
    'dos':          {'name': 'MS-DOS',             'extensions': ['.exe', '.com', '.bat', '.conf', '.zip', '.7z'], 'core': 'dosbox_pure_libretro.dll'},
    'pcengine':     {'name': 'PC Engine',          'extensions': ['.pce', '.cue', '.ccd', '.chd', '.zip', '.7z'], 'core': 'mednafen_pce_libretro.dll'},
    'famicom':      {'name': 'Famicom',            'extensions': ['.nes', '.fds', '.zip', '.7z'], 'core': 'fceumm_libretro.dll'},
    'fds':          {'name': 'Famicom Disk System', 'extensions': ['.fds', '.zip', '.7z'], 'core': 'fceumm_libretro.dll'},
    'channelf':     {'name': 'Fairchild Channel F', 'extensions': ['.bin', '.chf', '.zip', '.7z'], 'core': 'freechaf_libretro.dll'},
    'arcade':       {'name': 'Arcade',             'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'atomiswave':   {'name': 'Atomiswave',         'extensions': ['.zip', '.7z', '.bin', '.lst'], 'core': 'flycast_libretro.dll'},
    'daphne':       {'name': 'Daphne',             'extensions': ['.daphne', '.zip', '.7z'], 'core': 'daphne_libretro.dll'},
    'gameandwatch': {'name': 'Game & Watch',       'extensions': ['.mgw', '.zip', '.7z'], 'core': 'gw_libretro.dll'},
    'odyssey2':     {'name': 'Odyssey 2',          'extensions': ['.bin', '.zip', '.7z'], 'core': 'o2em_libretro.dll'},
    'vectrex':      {'name': 'Vectrex',            'extensions': ['.vec', '.bin', '.zip', '.7z'], 'core': 'vecx_libretro.dll'},
    'wonderswan':   {'name': 'WonderSwan',         'extensions': ['.ws', '.zip', '.7z'], 'core': 'mednafen_wswan_libretro.dll'},
    'wonderswanc':  {'name': 'WonderSwan Color',   'extensions': ['.wsc', '.zip', '.7z'], 'core': 'mednafen_wswan_libretro.dll'},
    'intellivision':{'name': 'Intellivision',      'extensions': ['.int', '.bin', '.rom', '.zip', '.7z'], 'core': 'freeintv_libretro.dll'},
    '3do':          {'name': '3DO',                'extensions': ['.iso', '.chd', '.cue', '.bin', '.zip', '.7z'], 'core': 'opera_libretro.dll'},
}

# LaunchBox full folder name → YancoHub system ID
# Allows scanning ROMs stored in LaunchBox's "Games" directory structure
_LB_FOLDER_TO_SYSTEM = {
    'Super Nintendo Entertainment System': 'snes',
    'Nintendo Entertainment System': 'nes',
    'Nintendo Game Boy Advance': 'gba',
    'Nintendo Game Boy': 'gb',
    'Nintendo Game Boy Color': 'gbc',
    'Nintendo 64': 'n64',
    'Nintendo DS': 'nds',
    'Sega Genesis': 'megadrive',
    'Sega Master System': 'mastersystem',
    'Sega Game Gear': 'gamegear',
    'Atari 2600': 'atari2600',
    'Sony PlayStation': 'psx',
    'Sony Playstation 2': 'ps2',
    'Sony Playstation 3': 'ps3',
    'Sony PSP': 'psp',
    'Sega Dreamcast': 'dreamcast',
    'Sega Saturn': 'saturn',
    'Nintendo GameCube': 'gamecube',
    'Nintendo Wii': 'wii',
    'SNK Neo Geo CD': 'neogeo',
    'SNK Neo Geo Pocket': 'ngp',
    'SNK Neo Geo Pocket Color': 'ngp',
    'Atari 5200': 'atari5200',
    'Atari 7800': 'atari7800',
    'Atari Lynx': 'atarilynx',
    'Atari ST': 'atarist',
    'Atari Jaguar': 'atarijaguar',
    'ColecoVision': 'colecovision',
    'Commodore 64': 'c64',
    'Commodore Amiga': 'amiga',
    'MS-DOS': 'dos',
    'NEC TurboGrafx-16': 'pcengine',
    'NEC TurboGrafx-CD': 'pcengine',
    'PC Engine SuperGrafx': 'pcengine',
    'Nintendo Famicom Disk System': 'fds',
    'Fairchild Channel F': 'channelf',
    'Nintendo Game & Watch': 'gameandwatch',
    'Magnavox Odyssey 2': 'odyssey2',
    'GCE Vectrex': 'vectrex',
    'WonderSwan': 'wonderswan',
    'WonderSwan Color': 'wonderswanc',
    'Mattel Intellivision': 'intellivision',
    '3DO Interactive Multiplayer': '3do',
}

IGNORE_EXTENSIONS = {'.txt', '.md', '.cfg', '.srm', '.sav', '.state', '.sta', '.xml',
                     '.log', '.ini', '.json', '.dat', '.bup', '.gitkeep',
                     '.html', '.url', '.sh', '.dll', '.lua', '.pat', '.input'}

# Format priority for deduplication (higher = preferred)
FORMAT_PRIORITY = {'.chd': 4, '.7z': 3, '.cue': 2, '.bin': 2, '.zip': 1}


def make_game_id(source, name):
    """Generate a stable game ID from source and name."""
    raw = f"{source}:{name}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def discover_launchbox_emulators(lb_path: str) -> dict[str, Path]:
    """Parse LaunchBox's Emulators.xml to discover installed emulators.

    Returns a dict mapping emulator name (lowercase) → exe Path.
    E.g. {'retroarch': Path('D:/.../retroarch.exe'), 'pcsx2': Path('D:/.../pcsx2-qt.exe')}
    """
    import xml.etree.ElementTree as ET

    result = {}
    lb = Path(lb_path)
    xml_file = lb / 'Data' / 'Emulators.xml'
    if not xml_file.exists():
        return result

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        for emu_el in root.findall('Emulator'):
            title = emu_el.findtext('Title', '').strip()
            app_path = emu_el.findtext('ApplicationPath', '').strip()
            if not title or not app_path:
                continue
            # Resolve relative paths against LaunchBox root
            exe_path = lb / app_path if not Path(app_path).is_absolute() else Path(app_path)
            if exe_path.exists():
                result[title.lower()] = exe_path
                logger.info(f"LaunchBox emulator: {title} → {exe_path}")
    except Exception as e:
        logger.warning(f"Failed to parse LaunchBox Emulators.xml: {e}")

    return result


class GameScanner:
    def __init__(self):
        self.games = []
        self._retroarch_path = None
        self._lb_emulators: dict[str, Path] = {}  # name → exe path

    def scan_all(self, rom_dirs=None, local_dirs=None):
        """Scan all game sources and return unified game list."""
        self.games = []
        logger.info("Starting full library scan...")

        self._scan_steam()
        self._scan_epic()
        self._scan_gog()
        self._scan_xbox()
        self._scan_ea()
        self._scan_ubisoft()
        self._scan_battlenet()

        if local_dirs:
            for d in local_dirs:
                self._scan_local_dir(d)

        if rom_dirs:
            for d in rom_dirs:
                self._scan_roms(d)

        logger.info(f"Scan complete: {len(self.games)} games found")
        return self.games

    # ── Direct exe detection helpers ───────────────────────────────────────

    # Executables that are never the main game
    _SKIP_EXE_NAMES = frozenset({
        'unins000', 'unins001', 'uninstall', 'setup', 'installer', 'install',
        'crash', 'crashhandler', 'crashreporter', 'crashpad_handler',
        'ue4prereqsetup', 'ueprereqsetup', 'ue4prereqsetup_x64',
        'unitycrashandler32', 'unitycrashandler64',
        'dxsetup', 'dxwebsetup', 'dotnetfx35setup', 'dotnetfx40setup',
        'vcredist_x86', 'vcredist_x64', 'vc_redist.x86', 'vc_redist.x64',
        'launch_game', 'launcher', 'easyanticheat_setup', 'easyanticheat',
        'battleye_installer', 'beclient_x64',
        'steamservice', 'steam_api', 'steam_api64',
        'python', 'pythonw', 'node', 'java', 'javaw',
    })

    # Subdirectories that contain redistributables, not game binaries
    _SKIP_EXE_DIRS = frozenset({
        '_commonredist', '__support', 'redist', 'redistributables',
        '_redist', 'directx', 'dotnet', 'vcredist', '__installer',
        'easyanticheat', 'battleye', 'support', 'installers',
    })

    def _find_game_exe(self, install_dir: str, game_name: str = '') -> str:
        """Find the most likely main game executable in an install directory.

        Returns the full path as a string, or '' if nothing convincing is found.
        Searches root + one level of subdirectories, skipping known tool/redist folders.
        """
        d = Path(install_dir)
        if not d.exists():
            return ''

        candidates = []
        game_lower = game_name.lower().replace(' ', '').replace('-', '').replace('_', '').replace(':', '')

        for exe in d.rglob('*.exe'):
            # Skip exes deeper than 2 levels (root + 1 subdir)
            try:
                rel = exe.relative_to(d)
            except ValueError:
                continue
            if len(rel.parts) > 2:
                continue

            # Skip exes inside known non-game directories
            if len(rel.parts) > 1 and rel.parts[0].lower() in self._SKIP_EXE_DIRS:
                continue

            stem = exe.stem.lower()
            if stem in self._SKIP_EXE_NAMES:
                continue
            # Skip common prefixes/patterns
            if stem.startswith(('unins', 'vc_redist', 'vcredist', 'dotnet')):
                continue

            try:
                size = exe.stat().st_size
            except OSError:
                continue

            # Score: name match is best, then file size, prefer root-level
            name_clean = stem.replace(' ', '').replace('-', '').replace('_', '').replace(':', '')
            name_match = (name_clean == game_lower) if game_lower else False
            depth = len(rel.parts) - 1  # 0 = root, 1 = subdir

            candidates.append((exe, name_match, depth, size))

        if not candidates:
            return ''

        # Sort: name match first, then shallowest, then largest
        candidates.sort(key=lambda c: (-c[1], c[2], -c[3]))
        return str(candidates[0][0])

    def _parse_gog_gameinfo(self, install_dir: str) -> tuple[str, str]:
        """Parse goggame-*.info files in a GOG game's install directory.

        Returns (exe_path, arguments) from the primary play task,
        or ('', '') if not found.
        """
        d = Path(install_dir)
        if not d.exists():
            return ('', '')

        for info_file in d.glob('goggame-*.info'):
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                tasks = data.get('playTasks', [])
                for task in tasks:
                    if task.get('isPrimary') and task.get('type') == 'FileTask':
                        rel_path = task.get('path', '')
                        if not rel_path:
                            continue
                        working_dir = task.get('workingDir', '')
                        base = d / working_dir if working_dir else d
                        exe_path = base / rel_path
                        if exe_path.exists():
                            args = task.get('arguments', '') or ''
                            return (str(exe_path), args)
            except Exception as e:
                logger.debug(f"Failed to parse {info_file.name}: {e}")

        return ('', '')

    # ── Steam ───────────────────────────────────────────────────────────────

    def _get_steam_path(self):
        """Get Steam installation path from registry."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            return Path(steam_path)
        except Exception as e:
            logger.debug(f"Steam registry lookup failed: {e}")
            # Fallback common paths
            for p in [Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam")]:
                if p.exists():
                    return p
        return None

    def _get_steam_library_folders(self, steam_path):
        """Parse libraryfolders.vdf for all Steam library locations."""
        folders = [steam_path]
        vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
        if not vdf_path.exists():
            return folders

        try:
            import vdf as vdf_lib
            with open(vdf_path, 'r', encoding='utf-8') as f:
                data = vdf_lib.load(f)
            lib_data = data.get('libraryfolders', data.get('LibraryFolders', {}))
            for key, value in lib_data.items():
                if key.isdigit() and isinstance(value, dict):
                    path = value.get('path', '')
                    if path and Path(path).exists():
                        folders.append(Path(path))
        except Exception as e:
            logger.warning(f"Failed to parse libraryfolders.vdf: {e}")

        return folders

    def _scan_steam(self):
        """Scan Steam for installed games."""
        steam_path = self._get_steam_path()
        if not steam_path:
            logger.info("Steam not found")
            return

        logger.info(f"Scanning Steam at {steam_path}")
        library_folders = self._get_steam_library_folders(steam_path)
        count = 0

        for lib_folder in library_folders:
            steamapps = lib_folder / "steamapps"
            if not steamapps.exists():
                continue

            for acf_file in steamapps.glob("appmanifest_*.acf"):
                try:
                    game = self._parse_acf(acf_file, steam_path)
                    if game:
                        self.games.append(game)
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse {acf_file}: {e}")

        logger.info(f"Steam: found {count} games")

    def _parse_acf(self, acf_path, steam_path):
        """Parse a Steam ACF manifest file using the vdf library."""
        import vdf as vdf_lib
        with open(acf_path, 'r', encoding='utf-8', errors='replace') as f:
            data = vdf_lib.load(f)
        app_state = data.get('AppState', {})

        appid = app_state.get('appid', '')
        name = app_state.get('name', '')

        if not appid or not name:
            return None

        # Skip Steam internals
        if name.lower() in ['steamworks common redistributables', 'steam linux runtime']:
            return None
        if 'proton' in name.lower() or 'redistributable' in name.lower():
            return None

        # Find artwork
        artwork_dir = steam_path / "appcache" / "librarycache"
        artwork = {}
        for art_type, patterns in {
            'header': [f'{appid}_header.jpg'],
            'cover': [f'{appid}_library_600x900.jpg', f'{appid}_library_600x900_2x.jpg'],
            'hero': [f'{appid}_library_hero.jpg'],
            'logo': [f'{appid}_logo.png'],
        }.items():
            for pat in patterns:
                art_path = artwork_dir / pat
                if art_path.exists():
                    artwork[art_type] = str(art_path)
                    break

        install_dir = acf_path.parent / "common" / app_state.get('installdir', '')
        size = int(app_state.get('SizeOnDisk', 0))
        install_str = str(install_dir) if install_dir.exists() else ''

        # Detect direct exe for native launch
        direct_exe = self._find_game_exe(install_str, name) if install_str else ''

        return {
            'id': f"steam_{appid}",
            'name': name,
            'source': 'steam',
            'appid': appid,
            'install_dir': install_str,
            'size': size,
            'artwork': artwork,
            'launch_cmd': f'steam://run/{appid}',
            'direct_exe': direct_exe,
        }

    # ── Epic Games Store ────────────────────────────────────────────────────

    def _scan_epic(self):
        """Scan Epic Games Store for installed games."""
        manifests_dir = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / \
                        "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
        if not manifests_dir.exists():
            logger.info("Epic Games Store not found")
            return

        logger.info(f"Scanning Epic at {manifests_dir}")
        count = 0

        for item_file in manifests_dir.glob("*.item"):
            try:
                with open(item_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                name = data.get('DisplayName', '')
                install_loc = data.get('InstallLocation', '')
                app_name = data.get('AppName', '')
                namespace = data.get('CatalogNamespace', '')

                if not name or not install_loc:
                    continue

                size = 0
                if install_loc and Path(install_loc).exists():
                    try:
                        size = int(data.get('InstallSize', 0))
                    except (ValueError, TypeError):
                        pass

                # Detect direct exe from Epic manifest
                direct_exe = ''
                direct_args = ''
                launch_exe = data.get('LaunchExecutable', '')
                if launch_exe and install_loc:
                    exe_path = Path(install_loc) / launch_exe
                    if exe_path.exists():
                        direct_exe = str(exe_path)
                        direct_args = data.get('LaunchCommand', '') or ''

                self.games.append({
                    'id': f"epic_{app_name or name}",
                    'name': name,
                    'source': 'epic',
                    'app_name': app_name,
                    'namespace': namespace,
                    'install_dir': install_loc,
                    'size': size,
                    'artwork': {},
                    'launch_cmd': f'com.epicgames.launcher://apps/{namespace}?action=launch&silent=true',
                    'direct_exe': direct_exe,
                    'direct_args': direct_args,
                })
                count += 1
            except Exception as e:
                logger.warning(f"Failed to parse Epic manifest {item_file}: {e}")

        logger.info(f"Epic: found {count} games")

    # ── GOG Galaxy ──────────────────────────────────────────────────────────

    def _scan_gog(self):
        """Scan GOG Galaxy for installed games."""
        count = 0

        # Try registry first
        try:
            import winreg
            gog_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     r"SOFTWARE\WOW6432Node\GOG.com\Games")
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(gog_key, i)
                    subkey = winreg.OpenKey(gog_key, subkey_name)
                    try:
                        name = winreg.QueryValueEx(subkey, "GAMENAME")[0]
                        path = winreg.QueryValueEx(subkey, "PATH")[0]
                        game_id = str(winreg.QueryValueEx(subkey, "GAMEID")[0])
                        exe = ''
                        try:
                            exe = winreg.QueryValueEx(subkey, "EXE")[0]
                        except FileNotFoundError:
                            pass

                        # GOG games are DRM-free — always detect direct exe
                        direct_exe = exe  # Registry exe is already direct
                        direct_args = ''
                        if not direct_exe and path:
                            # Try goggame-*.info for the exe path
                            direct_exe, direct_args = self._parse_gog_gameinfo(path)

                        self.games.append({
                            'id': f"gog_{game_id}",
                            'name': name,
                            'source': 'gog',
                            'install_dir': path,
                            'size': 0,
                            'artwork': {},
                            'launch_cmd': f'goggalaxy://openGameView/{game_id}',
                            'direct_exe': direct_exe,
                            'direct_args': direct_args,
                        })
                        count += 1
                    finally:
                        winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(gog_key)
        except Exception as e:
            logger.debug(f"GOG registry scan failed: {e}")

        # Try Galaxy database (read-only to avoid corrupting GOG's DB)
        db_path = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / \
                  "GOG.com" / "Galaxy" / "storage" / "galaxy-2.0.db"
        if db_path.exists() and count == 0:
            conn = None
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT releaseKey FROM LibraryReleases")
                existing_ids = {g['id'] for g in self.games if g['source'] == 'gog'}
                for (release_key,) in cursor.fetchall():
                    if '_' not in release_key:
                        continue
                    platform, game_id_raw = release_key.split('_', 1)
                    if platform != 'gog':
                        continue
                    gid = f"gog_{game_id_raw}"
                    if gid in existing_ids:
                        continue
                    # Try to get title from GamePieces
                    title = None
                    try:
                        cursor.execute("""
                            SELECT value FROM GamePieces
                            WHERE releaseKey = ? AND gamePieceTypeId IN (
                                SELECT id FROM GamePieceTypes WHERE type = 'title'
                            )
                        """, (release_key,))
                        row = cursor.fetchone()
                        if row:
                            data = json.loads(row[0])
                            title = data if isinstance(data, str) else data.get('title', '')
                    except Exception as e:
                        logger.debug(f"GOG GamePieces parse failed for {release_key}: {e}")
                    if not title:
                        title = game_id_raw.replace('_', ' ').title()

                    # Try to find install path from InstalledBaseProducts
                    install_dir = ''
                    direct_exe = ''
                    direct_args = ''
                    try:
                        cursor.execute(
                            "SELECT installationPath FROM InstalledBaseProducts WHERE productId = ?",
                            (game_id_raw,))
                        irow = cursor.fetchone()
                        if irow and irow[0]:
                            install_dir = irow[0]
                            direct_exe, direct_args = self._parse_gog_gameinfo(install_dir)
                    except Exception:
                        pass  # Table may not exist in all Galaxy DB versions

                    self.games.append({
                        'id': gid,
                        'name': title,
                        'source': 'gog',
                        'install_dir': install_dir,
                        'size': 0,
                        'artwork': {},
                        'launch_cmd': f'goggalaxy://openGameView/{game_id_raw}',
                        'direct_exe': direct_exe,
                        'direct_args': direct_args,
                    })
                    count += 1
            except sqlite3.OperationalError as e:
                logger.debug(f"GOG Galaxy DB scan failed (table missing?): {e}")
            except Exception as e:
                logger.debug(f"GOG Galaxy DB scan failed: {e}")
            finally:
                if conn:
                    conn.close()

        logger.info(f"GOG: found {count} games")

    # ── Xbox / Game Pass ────────────────────────────────────────────────────

    def _scan_xbox(self):
        """Scan Xbox/Game Pass for installed games."""
        count = 0

        # Scan XboxGames folder
        xbox_dirs = [
            Path("C:/XboxGames"),
            Path(os.environ.get('LOCALAPPDATA', '')) / "Packages",
        ]

        for xbox_dir in xbox_dirs:
            if not xbox_dir.exists():
                continue
            for game_dir in xbox_dir.iterdir():
                if not game_dir.is_dir():
                    continue
                name = game_dir.name
                # Skip system packages
                if name.startswith('Microsoft.') and 'Game' not in name:
                    continue
                if name.startswith(('windows.', 'Windows.', 'MicrosoftWindows')):
                    continue

                content_dir = game_dir / "Content"
                if content_dir.exists() or (game_dir / "gamelaunchhelper.exe").exists():
                    self.games.append({
                        'id': f"xbox_{make_game_id('xbox', name)}",
                        'name': self._clean_xbox_name(name),
                        'source': 'xbox',
                        'install_dir': str(game_dir),
                        'size': 0,
                        'artwork': {},
                        'launch_cmd': f'shell:AppsFolder\\{name}!App',
                    })
                    count += 1

        # Also try PowerShell to get Xbox apps
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-AppxPackage | Where-Object {$_.IsFramework -eq $false -and $_.SignatureKind -eq "Store"} | Select-Object Name, PackageFamilyName, InstallLocation | ConvertTo-Json'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                packages = json.loads(result.stdout)
                if isinstance(packages, dict):
                    packages = [packages]
                for pkg in packages:
                    name = pkg.get('Name', '')
                    # Filter to likely games (heuristic)
                    if any(x in name.lower() for x in ['game', 'xbox', 'ea.', 'bethesda', 'minecraft']):
                        pfn = pkg.get('PackageFamilyName', '')
                        if not any(g['id'] == f"xbox_{make_game_id('xbox', pfn)}" for g in self.games):
                            self.games.append({
                                'id': f"xbox_{make_game_id('xbox', pfn)}",
                                'name': self._clean_xbox_name(name),
                                'source': 'xbox',
                                'install_dir': pkg.get('InstallLocation', ''),
                                'size': 0,
                                'artwork': {},
                                'launch_cmd': f'shell:AppsFolder\\{pfn}!App',
                            })
                            count += 1
        except Exception as e:
            logger.debug(f"Xbox PowerShell scan failed: {e}")

        logger.info(f"Xbox/Game Pass: found {count} games")

    def _clean_xbox_name(self, raw_name):
        """Clean up Xbox package name to readable title."""
        # Remove publisher prefix (e.g., "BethesdaSoftworks.Starfield" → "Starfield")
        if '.' in raw_name:
            parts = raw_name.split('.')
            # Take everything after the first dot, rejoin
            name = ' '.join(parts[1:])
        else:
            name = raw_name
        # Remove version suffixes, underscores
        name = re.sub(r'_.*$', '', name)
        # Add spaces before capitals (CamelCase → Camel Case)
        name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
        return name.strip()

    # ── EA Play / EA Desktop ────────────────────────────────────────────────

    def _scan_ea(self):
        """Scan EA Desktop / Origin for installed games."""
        count = 0
        ea_dirs = [
            Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / "EA Desktop" / "InstallData",
            Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / "Origin" / "LocalContent",
        ]

        for ea_dir in ea_dirs:
            if not ea_dir.exists():
                continue
            for item in ea_dir.rglob("*.mfst"):
                try:
                    with open(item, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    # Parse manifest for game info
                    content_id = ''
                    match = re.search(r'id=(\S+)', content)
                    if match:
                        content_id = match.group(1)
                    if content_id:
                        # Try to get display name from nearby installer data
                        name = content_id.replace(':', ' ').replace('%20', ' ')
                        self.games.append({
                            'id': f"ea_{make_game_id('ea', content_id)}",
                            'name': name,
                            'source': 'ea',
                            'install_dir': str(item.parent),
                            'size': 0,
                            'artwork': {},
                            'launch_cmd': f'link2ea://launchgame/{content_id}',
                        })
                        count += 1
                except Exception as e:
                    logger.debug(f"EA manifest parse error: {e}")

        # Also check registry for EA/Origin games
        try:
            import winreg
            for base_key in [
                r"SOFTWARE\WOW6432Node\Electronic Arts",
                r"SOFTWARE\Electronic Arts",
            ]:
                try:
                    ea_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key)
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(ea_key, i)
                            subkey = winreg.OpenKey(ea_key, subkey_name)
                            try:
                                install_dir = winreg.QueryValueEx(subkey, "Install Dir")[0]
                                if Path(install_dir).exists():
                                    game_id = make_game_id('ea', subkey_name)
                                    if not any(g['id'] == f"ea_{game_id}" for g in self.games):
                                        self.games.append({
                                            'id': f"ea_{game_id}",
                                            'name': subkey_name,
                                            'source': 'ea',
                                            'install_dir': install_dir,
                                            'size': 0,
                                            'artwork': {},
                                            'launch_cmd': install_dir,
                                        })
                                        count += 1
                            except FileNotFoundError:
                                pass
                            finally:
                                winreg.CloseKey(subkey)
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(ea_key)
                except FileNotFoundError:
                    pass
        except Exception as e:
            logger.debug(f"EA registry scan failed: {e}")

        logger.info(f"EA: found {count} games")

    # ── Ubisoft Connect ─────────────────────────────────────────────────────

    def _scan_ubisoft(self):
        """Scan Ubisoft Connect for installed games."""
        count = 0

        try:
            import winreg
            ubi_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs")
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(ubi_key, i)
                    subkey = winreg.OpenKey(ubi_key, subkey_name)
                    try:
                        install_dir = winreg.QueryValueEx(subkey, "InstallDir")[0]
                        # Use folder name as game name
                        name = Path(install_dir).name if install_dir else subkey_name

                        self.games.append({
                            'id': f"ubisoft_{subkey_name}",
                            'name': name,
                            'source': 'ubisoft',
                            'install_dir': install_dir,
                            'size': 0,
                            'artwork': {},
                            'launch_cmd': f'uplay://launch/{subkey_name}/0',
                        })
                        count += 1
                    except FileNotFoundError:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(ubi_key)
        except Exception as e:
            logger.debug(f"Ubisoft registry scan failed: {e}")

        logger.info(f"Ubisoft: found {count} games")

    # ── Battle.net ──────────────────────────────────────────────────────────

    BATTLENET_PRODUCTS = {
        'Pro':  'Overwatch 2',
        'D3':   'Diablo III',
        'Fen':  'Diablo IV',
        'OSI':  'Diablo Immortal',
        'WTCG': 'Hearthstone',
        'Hero': 'Heroes of the Storm',
        'S2':   'StarCraft II',
        'S1':   'StarCraft Remastered',
        'W3':   'Warcraft III: Reforged',
        'WoW':  'World of Warcraft',
        'VIPR': 'Call of Duty',
        'ANBS': 'Diablo II: Resurrected',
    }

    def _scan_battlenet(self):
        """Scan Battle.net for installed games."""
        count = 0
        bnet_config = Path(os.environ.get('APPDATA', '')) / "Battle.net" / "Battle.net.config"

        if not bnet_config.exists():
            logger.info("Battle.net not found")
            return

        try:
            with open(bnet_config, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Check for installed games in config
            games_installed = config.get('Games', {})
            for code, info in games_installed.items():
                if isinstance(info, dict) and info.get('ServerUid'):
                    install_dir = info.get('Client', {}).get('Install', {}).get('DefaultInstallPath', '')
                    name = self.BATTLENET_PRODUCTS.get(code, code)

                    self.games.append({
                        'id': f"bnet_{code}",
                        'name': name,
                        'source': 'battlenet',
                        'install_dir': install_dir,
                        'size': 0,
                        'artwork': {},
                        'launch_cmd': f'battlenet://{code}',
                    })
                    count += 1
        except Exception as e:
            logger.debug(f"Battle.net config parse failed: {e}")

        logger.info(f"Battle.net: found {count} games")

    # ── Local Games ─────────────────────────────────────────────────────────

    def _scan_local_dir(self, directory):
        """Scan a local directory for game executables."""
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Local game dir not found: {directory}")
            return

        count = 0
        # Look for .exe files in immediate subdirectories (each subfolder = one game)
        for game_dir in dir_path.iterdir():
            if not game_dir.is_dir():
                continue

            # Find the main .exe (largest exe, or one matching folder name)
            exes = list(game_dir.glob("*.exe"))
            if not exes:
                # Check one level deeper
                exes = list(game_dir.glob("*/*.exe"))
            if not exes:
                continue

            # Prefer exe matching folder name, else largest
            name = game_dir.name
            best_exe = None
            for exe in exes:
                if exe.stem.lower() == name.lower():
                    best_exe = exe
                    break
            if not best_exe:
                # Pick largest exe (likely the game, not uninstaller/launcher)
                best_exe = max(exes, key=lambda e: e.stat().st_size)

            # Skip obvious non-game exes
            skip_names = {'unins000', 'uninstall', 'setup', 'installer', 'crash', 'ue4prereqsetup'}
            if best_exe.stem.lower() in skip_names:
                other_exes = [e for e in exes if e.stem.lower() not in skip_names]
                if other_exes:
                    best_exe = max(other_exes, key=lambda e: e.stat().st_size)
                else:
                    continue

            self.games.append({
                'id': f"local_{make_game_id('local', name)}",
                'name': name,
                'source': 'local',
                'install_dir': str(game_dir),
                'size': 0,
                'artwork': {},
                'launch_cmd': str(best_exe),
            })
            count += 1

        logger.info(f"Local ({directory}): found {count} games")

    # ── Retro ROMs ──────────────────────────────────────────────────────────

    def _find_retroarch(self):
        """Find RetroArch installation on Windows.

        Checks: manually set path → LaunchBox emulators → standard locations → PATH.
        """
        if self._retroarch_path:
            return self._retroarch_path

        # Check YancoHub's managed emulators directory
        managed = Path(__file__).parent / 'emulators' / 'retroarch'
        if (managed / 'retroarch.exe').exists():
            self._retroarch_path = managed
            logger.info(f"Using YancoHub managed RetroArch: {managed}")
            return managed

        # Check LaunchBox-discovered emulators
        if 'retroarch' in self._lb_emulators:
            ra_exe = self._lb_emulators['retroarch']
            self._retroarch_path = ra_exe.parent
            logger.info(f"Using LaunchBox RetroArch: {self._retroarch_path}")
            return self._retroarch_path

        candidates = [
            Path(os.environ.get('PROGRAMFILES', '')) / "RetroArch",
            Path(os.environ.get('PROGRAMFILES(X86)', '')) / "RetroArch",
            Path(os.environ.get('LOCALAPPDATA', '')) / "RetroArch",
            Path(os.environ.get('APPDATA', '')) / "RetroArch",
            Path("C:/RetroArch"),
            Path("C:/RetroArch-Win64"),
        ]

        for p in candidates:
            if (p / "retroarch.exe").exists():
                self._retroarch_path = p
                return p

        # Check PATH
        import shutil
        ra = shutil.which("retroarch")
        if ra:
            self._retroarch_path = Path(ra).parent
            return self._retroarch_path

        return None

    def _scan_roms(self, rom_base_dir):
        """Scan a ROM directory for retro games.

        Supports both short system ID folders (e.g. 'snes') and
        LaunchBox-style full-name folders (e.g. 'Super Nintendo Entertainment System').
        """
        rom_base = Path(rom_base_dir)
        if not rom_base.exists():
            logger.warning(f"ROM directory not found: {rom_base_dir}")
            return

        retroarch_path = self._find_retroarch()
        total = 0

        # Build reverse map: system_id → list of folder names to try
        system_folders: dict[str, list[Path]] = {}
        for system_id in ROM_SYSTEMS:
            folders = []
            short_dir = rom_base / system_id
            if short_dir.exists():
                folders.append(short_dir)
            system_folders[system_id] = folders

        # Add LaunchBox full-name folders
        for lb_name, system_id in _LB_FOLDER_TO_SYSTEM.items():
            if system_id in ROM_SYSTEMS:
                lb_dir = rom_base / lb_name
                if lb_dir.exists() and lb_dir not in system_folders.get(system_id, []):
                    system_folders.setdefault(system_id, []).append(lb_dir)

        for system_id, system_info in ROM_SYSTEMS.items():
            dirs_to_scan = system_folders.get(system_id, [])
            if not dirs_to_scan:
                continue

            valid_exts = set(system_info['extensions'])
            seen_games = {}  # name → (path, priority) for dedup

            for system_dir in dirs_to_scan:
                for rom_file in system_dir.iterdir():
                    if not rom_file.is_file():
                        continue

                    ext = rom_file.suffix.lower()
                    if ext in IGNORE_EXTENSIONS:
                        continue
                    if ext not in valid_exts:
                        continue

                    # Clean name for dedup
                    clean_name = rom_file.stem
                    # Remove region tags, disc numbers for dedup
                    base_name = re.sub(r'\s*[\(\[].*?[\)\]]', '', clean_name).strip()

                    priority = FORMAT_PRIORITY.get(ext, 0)

                    if base_name in seen_games:
                        existing_priority = seen_games[base_name][1]
                        if priority <= existing_priority:
                            continue
                        # Remove old entry
                        old_id = f"rom_{make_game_id(system_id, seen_games[base_name][0].name)}"
                        self.games = [g for g in self.games if g['id'] != old_id]

                    seen_games[base_name] = (rom_file, priority)

                    # Build launch command
                    launch_cmd = self._build_rom_launch_cmd(system_id, system_info,
                                                             str(rom_file), retroarch_path)

                    self.games.append({
                        'id': f"rom_{make_game_id(system_id, rom_file.name)}",
                        'name': clean_name,
                        'source': 'retro',
                        'system': system_id,
                        'system_name': system_info['name'],
                        'file_path': str(rom_file),
                        'size': rom_file.stat().st_size,
                        'artwork': {},
                        'launch_cmd': launch_cmd,
                    })
                    total += 1

        logger.info(f"ROMs ({rom_base_dir}): found {total} games")

    def _find_standalone_emulator(self, emulator: str, rom_path: str) -> str | None:
        """Try to find a standalone emulator (LaunchBox → system install).

        Returns a launch command string, or None to fall through to RetroArch.
        """
        if not emulator:
            return None

        if emulator == 'pcsx2':
            if 'pcsx2' in self._lb_emulators:
                return f'"{self._lb_emulators["pcsx2"]}" -fullscreen -nogui "{rom_path}"'
            for p in [Path("C:/Program Files/PCSX2"), Path("C:/Program Files (x86)/PCSX2")]:
                exe = p / "pcsx2-qt.exe"
                if exe.exists():
                    return f'"{exe}" -fullscreen -batch "{rom_path}"'

        elif emulator == 'dolphin':
            if 'dolphin' in self._lb_emulators:
                return f'"{self._lb_emulators["dolphin"]}" -b -e "{rom_path}"'
            for p in [Path("C:/Program Files/Dolphin"), Path("C:/Program Files (x86)/Dolphin")]:
                exe = p / "Dolphin.exe"
                if exe.exists():
                    return f'"{exe}" -b -e "{rom_path}"'

        elif emulator == 'ppsspp':
            if 'ppsspp' in self._lb_emulators:
                return f'"{self._lb_emulators["ppsspp"]}" "{rom_path}"'
            for p in [Path("C:/Program Files/PPSSPP"), Path("C:/Program Files (x86)/PPSSPP")]:
                exe = p / "PPSSPPWindows64.exe"
                if exe.exists():
                    return f'"{exe}" "{rom_path}"'

        elif emulator == 'rpcs3':
            if 'rpcs3' in self._lb_emulators:
                return f'"{self._lb_emulators["rpcs3"]}" --no-gui "{rom_path}"'
            for p in [Path("C:/Program Files/RPCS3"), Path("C:/RPCS3")]:
                exe = p / "rpcs3.exe"
                if exe.exists():
                    return f'"{exe}" --no-gui "{rom_path}"'

        return None  # Fall through to RetroArch

    def _build_rom_launch_cmd(self, system_id, system_info, rom_path, retroarch_path):
        """Build the launch command for a ROM.

        Priority: LaunchBox standalone emulator → system install → RetroArch core.
        Users don't need to install anything if LaunchBox has RetroArch with cores.
        """
        emulator = system_info.get('emulator', '')

        # ── Standalone emulator lookup (preferred for PS2, GC, Wii) ──
        standalone_cmd = self._find_standalone_emulator(emulator, rom_path)
        if standalone_cmd:
            return standalone_cmd

        # ── Fall through to RetroArch core (works for everything) ──
        if 'core' in system_info and retroarch_path:
            core = system_info['core']
            core_path = retroarch_path / "cores" / core
            retroarch_exe = retroarch_path / "retroarch.exe"
            return f'"{retroarch_exe}" -L "{core_path}" "{rom_path}"'

        return f'retroarch.exe -L cores/{system_info.get("core", "")} "{rom_path}"'

    # ── Store detection ─────────────────────────────────────────────────────

    def get_detected_stores(self):
        """Return which game stores are detected on this system."""
        stores = {}

        stores['steam'] = self._get_steam_path() is not None

        epic_dir = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / \
                   "Epic" / "EpicGamesLauncher"
        stores['epic'] = epic_dir.exists()

        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\WOW6432Node\GOG.com\Games")
            winreg.CloseKey(key)
            stores['gog'] = True
        except Exception:
            gog_db = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / \
                     "GOG.com" / "Galaxy" / "storage" / "galaxy-2.0.db"
            stores['gog'] = gog_db.exists()

        stores['xbox'] = Path("C:/XboxGames").exists()

        ea_dir = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / "EA Desktop"
        origin_dir = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / "Origin"
        stores['ea'] = ea_dir.exists() or origin_dir.exists()

        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\WOW6432Node\Ubisoft\Launcher")
            winreg.CloseKey(key)
            stores['ubisoft'] = True
        except Exception:
            stores['ubisoft'] = False

        bnet_config = Path(os.environ.get('APPDATA', '')) / "Battle.net"
        stores['battlenet'] = bnet_config.exists()

        stores['retroarch'] = self._find_retroarch() is not None

        return stores
