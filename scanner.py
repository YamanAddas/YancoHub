"""
YancoHub Game Library Scanner — Windows
Discovers games from Steam, Epic, GOG, Xbox/Game Pass, EA, Ubisoft, Battle.net,
local directories, and retro ROMs.
"""

import os
import re
import json
import glob
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
    'ps2':          {'name': 'PlayStation 2',       'extensions': ['.chd', '.iso', '.bin', '.cue', '.7z'], 'emulator': 'pcsx2'},
    'ps3':          {'name': 'PlayStation 3',       'extensions': ['.bin'], 'emulator': 'rpcs3'},  # EBOOT.BIN
    'psp':          {'name': 'PlayStation Portable','extensions': ['.iso', '.cso', '.pbp', '.7z'], 'emulator': 'ppsspp'},
    'dreamcast':    {'name': 'Sega Dreamcast',     'extensions': ['.chd', '.cdi', '.gdi', '.zip', '.7z'], 'core': 'flycast_libretro.dll'},
    'saturn':       {'name': 'Sega Saturn',        'extensions': ['.chd', '.bin', '.cue', '.iso', '.7z'], 'core': 'mednafen_saturn_libretro.dll'},
    'gamecube':     {'name': 'GameCube',           'extensions': ['.iso', '.gcm', '.rvz', '.nkit.iso', '.7z'], 'emulator': 'dolphin'},
    'wii':          {'name': 'Nintendo Wii',       'extensions': ['.iso', '.wbfs', '.rvz', '.wad', '.nkit.iso', '.7z'], 'emulator': 'dolphin'},
    'neogeo':       {'name': 'Neo Geo',            'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'fbneo':        {'name': 'FinalBurn Neo',      'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'cps1':         {'name': 'CPS-1',              'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'cps2':         {'name': 'CPS-2',              'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'cps3':         {'name': 'CPS-3',              'extensions': ['.zip', '.7z'], 'core': 'fbneo_libretro.dll'},
    'mame':         {'name': 'MAME',               'extensions': ['.zip', '.7z'], 'core': 'mame_libretro.dll'},
    'ngp':          {'name': 'Neo Geo Pocket',     'extensions': ['.ngp', '.ngc', '.zip', '.7z'], 'core': 'mednafen_ngp_libretro.dll'},
}

IGNORE_EXTENSIONS = {'.txt', '.md', '.cfg', '.srm', '.sav', '.state', '.xml',
                     '.log', '.ini', '.json', '.dat', '.bup', '.gitkeep',
                     '.html', '.url', '.sh', '.dll', '.lua', '.pat', '.input'}

# Format priority for deduplication (higher = preferred)
FORMAT_PRIORITY = {'.chd': 4, '.7z': 3, '.cue': 2, '.bin': 2, '.zip': 1}


def make_game_id(source, name):
    """Generate a stable game ID from source and name."""
    raw = f"{source}:{name}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


class GameScanner:
    def __init__(self):
        self.games = []
        self._retroarch_path = None

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

    # ── Steam ───────────────────────────────────────────────────────────────

    def _get_steam_path(self):
        """Get Steam installation path from registry."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            return Path(steam_path)
        except Exception:
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
        """Parse a Steam ACF manifest file."""
        data = {}
        with open(acf_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if line.startswith('"') and '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        key = parts[0].strip('"')
                        val = parts[-1].strip('"')
                        data[key] = val

        appid = data.get('appid', '')
        name = data.get('name', '')

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

        install_dir = acf_path.parent / "common" / data.get('installdir', '')
        size = int(data.get('SizeOnDisk', 0))

        return {
            'id': f"steam_{appid}",
            'name': name,
            'source': 'steam',
            'appid': appid,
            'install_dir': str(install_dir) if install_dir.exists() else '',
            'size': size,
            'artwork': artwork,
            'launch_cmd': f'steam://run/{appid}',
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

                self.games.append({
                    'id': f"epic_{make_game_id('epic', app_name or name)}",
                    'name': name,
                    'source': 'epic',
                    'app_name': app_name,
                    'namespace': namespace,
                    'install_dir': install_loc,
                    'size': size,
                    'artwork': {},
                    'launch_cmd': f'com.epicgames.launcher://apps/{namespace}?action=launch&silent=true',
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
                        game_id = winreg.QueryValueEx(subkey, "GAMEID")[0]
                        exe = ''
                        try:
                            exe = winreg.QueryValueEx(subkey, "EXE")[0]
                        except FileNotFoundError:
                            pass

                        self.games.append({
                            'id': f"gog_{game_id}",
                            'name': name,
                            'source': 'gog',
                            'install_dir': path,
                            'size': 0,
                            'artwork': {},
                            'launch_cmd': exe if exe else f'goggalaxy://openGameView/{game_id}',
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

        # Try Galaxy database
        db_path = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / \
                  "GOG.com" / "Galaxy" / "storage" / "galaxy-2.0.db"
        if db_path.exists() and count == 0:
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT productId, title
                    FROM InstalledBaseProducts
                    WHERE isInstalled = 1
                """)
                for row in cursor.fetchall():
                    prod_id, title = row
                    self.games.append({
                        'id': f"gog_{prod_id}",
                        'name': title,
                        'source': 'gog',
                        'install_dir': '',
                        'size': 0,
                        'artwork': {},
                        'launch_cmd': f'goggalaxy://openGameView/{prod_id}',
                    })
                    count += 1
                conn.close()
            except Exception as e:
                logger.debug(f"GOG Galaxy DB scan failed: {e}")

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
        """Find RetroArch installation on Windows."""
        if self._retroarch_path:
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
        """Scan a ROM directory for retro games."""
        rom_base = Path(rom_base_dir)
        if not rom_base.exists():
            logger.warning(f"ROM directory not found: {rom_base_dir}")
            return

        retroarch_path = self._find_retroarch()
        total = 0

        for system_id, system_info in ROM_SYSTEMS.items():
            system_dir = rom_base / system_id
            if not system_dir.exists():
                continue

            valid_exts = set(system_info['extensions'])
            seen_games = {}  # name → (path, priority) for dedup

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

    def _build_rom_launch_cmd(self, system_id, system_info, rom_path, retroarch_path):
        """Build the launch command for a ROM."""
        emulator = system_info.get('emulator', '')

        if emulator == 'pcsx2':
            # Look for PCSX2 on Windows
            for p in [Path("C:/Program Files/PCSX2"), Path("C:/Program Files (x86)/PCSX2")]:
                exe = p / "pcsx2-qt.exe"
                if exe.exists():
                    return f'"{exe}" -fullscreen -batch "{rom_path}"'
            return f'pcsx2-qt.exe -fullscreen -batch "{rom_path}"'

        elif emulator == 'dolphin':
            for p in [Path("C:/Program Files/Dolphin"), Path("C:/Program Files (x86)/Dolphin")]:
                exe = p / "Dolphin.exe"
                if exe.exists():
                    return f'"{exe}" -b -e "{rom_path}"'
            return f'Dolphin.exe -b -e "{rom_path}"'

        elif emulator == 'ppsspp':
            for p in [Path("C:/Program Files/PPSSPP"), Path("C:/Program Files (x86)/PPSSPP")]:
                exe = p / "PPSSPPWindows64.exe"
                if exe.exists():
                    return f'"{exe}" "{rom_path}"'
            return f'PPSSPPWindows64.exe "{rom_path}"'

        elif emulator == 'rpcs3':
            for p in [Path("C:/Program Files/RPCS3"), Path("C:/RPCS3")]:
                exe = p / "rpcs3.exe"
                if exe.exists():
                    return f'"{exe}" --no-gui "{rom_path}"'
            return f'rpcs3.exe --no-gui "{rom_path}"'

        elif 'core' in system_info and retroarch_path:
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
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                          r"SOFTWARE\WOW6432Node\GOG.com\Games")
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
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                          r"SOFTWARE\WOW6432Node\Ubisoft\Launcher")
            stores['ubisoft'] = True
        except Exception:
            stores['ubisoft'] = False

        bnet_config = Path(os.environ.get('APPDATA', '')) / "Battle.net"
        stores['battlenet'] = bnet_config.exists()

        stores['retroarch'] = self._find_retroarch() is not None

        return stores
