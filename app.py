"""
YancoHub — Flask Backend
Unified game launcher for Windows with CatByte AI companion.
"""

import os
import json
import time
import atexit
import logging
import shlex
import subprocess
import threading
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_file, abort

from scanner import GameScanner, discover_launchbox_emulators
from emusetup import EmulatorSetup
from userdata import UserData
from catbyte import CatByte
from chathistory import ChatHistory
from accounts import SteamAccount, GogGalaxyDB, EpicCatalogDB, EpicAccount, resolve_steam_vanity_url, detect_steam_users
from metadata import MetadataFetcher
from artwork import ArtworkScraper
from biosmanager import BIOSManager
from constants import VALID_ART_TYPES, FLASK_PORT

# ── Logging ─────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'yancohub.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('yancohub')

# ── App Setup ───────────────────────────────────────────────────────────────

app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

scanner = GameScanner()
userdata = UserData()
atexit.register(userdata.flush)
catbyte = CatByte()
chat_history = ChatHistory()
metadata_fetcher = MetadataFetcher()
artwork_scraper = ArtworkScraper(
    launchbox_path=userdata.get_settings().get('launchbox_path', ''),
)
bios_manager = BIOSManager()
emu_setup = EmulatorSetup()

# Discover emulators from LaunchBox (if configured)
_lb_setting = userdata.get_settings().get('launchbox_path', '')
if _lb_setting:
    # Resolve to LB root (user may have pointed to Images/ or other subfolder)
    _lb_root = artwork_scraper._resolve_lb_root(_lb_setting)
    if _lb_root:
        scanner._lb_emulators = discover_launchbox_emulators(str(_lb_root))

# Initialize RetroArch path from settings
_ra_path = userdata.get_settings().get('retroarch_path', '')
if _ra_path and Path(_ra_path).exists():
    scanner._retroarch_path = Path(_ra_path).parent if _ra_path.lower().endswith('.exe') else Path(_ra_path)

# Initialize BIOS dirs from settings
_bios_dirs = userdata.get_settings().get('bios_dirs', [])
if _bios_dirs:
    bios_manager.set_bios_dirs(_bios_dirs)

# Initialize CatByte from saved config
_catbyte_config = userdata.get_catbyte_config()
if _catbyte_config:
    catbyte.configure(_catbyte_config)

# In-memory game library (refreshed on scan)
game_library = []
game_index = {}  # id → game dict
_library_lock = threading.Lock()

# Active game process tracking
active_process = None
active_game_id = None
_active_lock = threading.Lock()

# Scan completion flag
scan_complete = False

# Allowed origins for POST requests (CSRF protection)
_ALLOWED_ORIGINS = {
    f'http://127.0.0.1:{FLASK_PORT}',
    f'http://localhost:{FLASK_PORT}',
}


@app.before_request
def _check_origin():
    """Block cross-origin POST requests to prevent CSRF attacks."""
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    origin = request.headers.get('Origin') or request.headers.get('Referer', '')
    # Strip path from Referer to get origin
    if '://' in origin:
        parts = origin.split('/')
        origin = '/'.join(parts[:3])
    if origin and origin not in _ALLOWED_ORIGINS:
        return jsonify({'error': 'Forbidden — invalid origin'}), 403


# ── Path validation (BUG-033/034) ─────────────────────────────────────────

# System directories that should never be scanned
_BLOCKED_DIRS = {
    Path(os.environ.get('SYSTEMROOT', r'C:\Windows')).resolve(),
    Path(os.environ.get('SYSTEMROOT', r'C:\Windows')).resolve() / 'System32',
}


def _validate_dir_path(path_str: str) -> str | None:
    """Validate a user-provided directory path. Returns error message or None if valid."""
    try:
        p = Path(path_str).resolve()
    except (ValueError, OSError):
        return 'Invalid path'
    if not p.is_dir():
        return 'Path is not an existing directory'
    if p in _BLOCKED_DIRS or any(p == b or b in p.parents for b in _BLOCKED_DIRS):
        return 'Cannot scan system directories'
    return None


def _validate_file_within_dirs(file_path: str, allowed_dirs: list[str]) -> bool:
    """Check that a resolved file path is inside one of the allowed directories."""
    try:
        resolved = Path(file_path).resolve(strict=True)
        for d in allowed_dirs:
            if resolved.is_relative_to(Path(d).resolve()):
                return True
    except (ValueError, OSError):
        pass
    return False


def _set_active(proc, gid):
    global active_process, active_game_id
    with _active_lock:
        active_process = proc
        active_game_id = gid


def _clear_active(gid):
    global active_process, active_game_id
    with _active_lock:
        if active_game_id == gid:
            active_process = None
            active_game_id = None


def _get_active():
    with _active_lock:
        return active_process, active_game_id


def _build_library():
    """Scan all sources (local + accounts) and build the game index."""
    global game_library, game_index

    # 1. Local scan (installed games)
    local_games = scanner.scan_all(
        rom_dirs=userdata.get_rom_dirs(),
        local_dirs=userdata.get_local_dirs(),
    )
    # Mark all local games as installed
    for g in local_games:
        g['installed'] = True

    # 2. Steam account (all owned games)
    steam_config = userdata.get_steam_account()
    account_games = []
    if steam_config.get('connected') and steam_config.get('api_key') and steam_config.get('steam_id'):
        try:
            steam = SteamAccount(steam_config['api_key'], steam_config['steam_id'])
            steam_games = steam.get_owned_games()
            account_games.extend(steam_games)
            logger.info(f"Steam account: {len(steam_games)} owned games")
        except Exception as e:
            logger.error(f"Steam account fetch failed: {e}")

    # 3. Epic catalog (local cache — works automatically like GOG Galaxy)
    epic_catalog = EpicCatalogDB()
    if epic_catalog.is_available():
        try:
            epic_games = epic_catalog.get_all_games()
            account_games.extend(epic_games)
            logger.info(f"Epic catalog: {len(epic_games)} owned games")
        except Exception as e:
            logger.error(f"Epic catalog read failed: {e}")
    elif EpicAccount.is_authenticated():
        # Fallback to legendary if catalog cache not available
        try:
            epic_games = EpicAccount.get_owned_games()
            account_games.extend(epic_games)
            logger.info(f"Epic (legendary): {len(epic_games)} owned games")
        except Exception as e:
            logger.error(f"Epic account fetch failed: {e}")

    # 4. GOG Galaxy database
    galaxy_config = userdata.get_gog_galaxy_config()
    galaxy_db = GogGalaxyDB(galaxy_config.get('db_path') or None)
    if galaxy_config.get('enabled', False) or galaxy_db.is_available():
        try:
            galaxy_games = galaxy_db.get_all_games()
            account_games.extend(galaxy_games)
            logger.info(f"GOG Galaxy: {len(galaxy_games)} games")
            # Auto-enable if found
            if galaxy_db.is_available() and not galaxy_config.get('enabled'):
                userdata.set_gog_galaxy_enabled(True, str(galaxy_db.db_path))
        except Exception as e:
            logger.error(f"GOG Galaxy DB read failed: {e}")

    # 4. Merge: local games take priority over account games (by ID and name)
    merged = {g['id']: g for g in local_games}
    local_names = {g['name'].lower() for g in local_games}

    show_uninstalled = userdata.get_settings().get('show_uninstalled', True)

    for ag in account_games:
        if ag['id'] in merged:
            # Local version exists — merge artwork from account if local is missing
            local_game = merged[ag['id']]
            if not local_game.get('artwork') or not any(local_game['artwork'].values()):
                local_game['artwork'] = ag.get('artwork', {})
            # Merge API playtime if available
            if ag.get('playtime_from_api'):
                local_game['playtime_from_api'] = ag['playtime_from_api']
            continue

        # Check by name match (different IDs but same game)
        if ag['name'].lower() in local_names:
            continue

        # New game from account — only add if show_uninstalled is on
        if show_uninstalled:
            ag['installed'] = False
            merged[ag['id']] = ag

    new_library = list(merged.values())
    new_index = {g['id']: g for g in new_library}

    with _library_lock:
        game_library = new_library
        game_index = new_index

    logger.info(f"Library built: {len(new_library)} games ({len(local_games)} installed, {len(new_library) - len(local_games)} from accounts)")

    # Background: pre-warm artwork title cache, enrich metadata, fetch artwork
    def _enrich():
        try:
            artwork_scraper.prewarm_title_cache(new_library)
        except Exception as e:
            logger.debug(f"Title cache prewarm error: {e}")
        try:
            metadata_fetcher.enrich_games(new_library[:50])  # First 50 to avoid rate limits
        except Exception as e:
            logger.debug(f"Metadata enrichment error: {e}")
        try:
            artwork_scraper.fetch_for_games(new_library[:100])
        except Exception as e:
            logger.debug(f"Artwork fetch error: {e}")
    threading.Thread(target=_enrich, daemon=True).start()


# Initial scan in background
def _initial_scan():
    global scan_complete
    try:
        _build_library()
    except Exception as e:
        logger.error(f"Initial scan failed: {e}")
    finally:
        scan_complete = True
        logger.info("Initial scan complete")

scan_thread = threading.Thread(target=_initial_scan, daemon=True)
scan_thread.start()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    with _library_lock:
        count = len(game_library)
    return jsonify({'status': 'ok', 'games': count})


# ── Games API ───────────────────────────────────────────────────────────────

@app.route('/api/games')
def api_games():
    if not scan_complete:
        return jsonify({'status': 'scanning', 'games': []})

    source = request.args.get('source', '')
    system = request.args.get('system', '')
    hidden = set(userdata.get_hidden_systems())
    playtime = userdata.get_playtime()
    favorites = set(userdata.get_favorites())

    with _library_lock:
        snapshot = list(game_library)

    results = []
    for game in snapshot:
        # Filter by source
        if source and game['source'] != source:
            continue
        # Filter by system (retro only)
        if system and game.get('system', '') != system:
            continue
        # Hide hidden systems
        if game.get('system') in hidden:
            continue

        # Enrich with user data
        enriched = dict(game)
        pt = playtime.get(game['id'], {})
        enriched['playtime_hours'] = pt.get('total_hours', 0)
        enriched['last_played'] = pt.get('last_played')
        enriched['is_favorite'] = game['id'] in favorites

        # Enrich with cached metadata (non-blocking, only if already cached)
        meta = metadata_fetcher.db.get(game['id'])
        if meta:
            enriched['description'] = meta.get('description', '')
            enriched['genre'] = meta.get('genre', '')
            enriched['developer'] = meta.get('developer', '')
            enriched['publisher'] = meta.get('publisher', '')
            enriched['release_year'] = meta.get('release_year')
            enriched['community_rating'] = meta.get('rating')

        results.append(enriched)

    return jsonify(results)


@app.route('/api/artwork/<game_id>/<art_type>')
def api_artwork(game_id, art_type):
    if art_type not in VALID_ART_TYPES:
        abort(400)
    with _library_lock:
        game = game_index.get(game_id)
    if not game:
        abort(404)

    def _send_artwork(path: str):
        """Send an artwork file with cache headers."""
        try:
            resp = send_file(path)
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            return resp
        except (FileNotFoundError, OSError):
            abort(404)

    # 1. Check game's own artwork dict (local Steam files)
    artwork_path = game.get('artwork', {}).get(art_type, '')
    if artwork_path and not artwork_path.startswith('http') and Path(artwork_path).exists():
        return _send_artwork(artwork_path)

    # 2. Use the artwork scraper (checks cache, then fetches)
    scraped = artwork_scraper.get_artwork_path(game, art_type)
    if scraped and Path(scraped).exists():
        return _send_artwork(scraped)

    # 3. Fallback: try remote URL from game data
    if artwork_path and artwork_path.startswith('http'):
        downloaded = artwork_scraper._download_and_cache(game_id, art_type, artwork_path)
        if downloaded:
            return _send_artwork(downloaded)

    abort(404)


@app.route('/api/platform-artwork/<system>')
def api_platform_artwork(system):
    """Serve console/platform artwork from LaunchBox Images/Platforms/ folder."""
    path = artwork_scraper.get_platform_artwork(system)
    if path and Path(path).exists():
        try:
            resp = send_file(path)
            resp.headers['Cache-Control'] = 'public, max-age=604800'
            return resp
        except (FileNotFoundError, OSError):
            pass
    abort(404)


@app.route('/api/launch/<game_id>', methods=['POST'])
def api_launch(game_id):
    with _library_lock:
        game = game_index.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    launch_cmd = game.get('launch_cmd', '')
    if not launch_cmd:
        return jsonify({'error': 'No launch command'}), 400

    logger.info(f"Launching: {game['name']} [{game['source']}]")
    userdata.session_start(game_id)

    try:
        # Check if direct launch is enabled (per-game override > global setting)
        override = userdata.get_direct_launch_override(game_id)
        if override is not None:
            direct_launch = override
        else:
            direct_launch = userdata.get_settings().get('direct_launch', True)
        direct_exe = game.get('direct_exe', '')
        use_direct = direct_launch and direct_exe and Path(direct_exe).exists()

        if use_direct:
            # Direct executable launch — bypasses store client
            # For Steam games, ensure steam_appid.txt exists so Steamworks SDK can init
            if game.get('source') == 'steam' and game.get('appid'):
                appid_file = Path(direct_exe).parent / 'steam_appid.txt'
                if not appid_file.exists():
                    try:
                        appid_file.write_text(str(game['appid']), encoding='utf-8')
                        logger.info(f"Created {appid_file}")
                    except OSError as e:
                        logger.debug(f"Could not create steam_appid.txt: {e}")

            # Use exe path as-is (not shlex.split) to preserve Windows paths with spaces
            args = [direct_exe]
            direct_args = game.get('direct_args', '')
            if direct_args:
                args.extend(shlex.split(direct_args, posix=False))
            proc = subprocess.Popen(
                args,
                shell=False,
                cwd=game.get('install_dir', None) or None,
            )
            _set_active(proc, game_id)
            # If process dies within 5s (likely DRM failure), fall back to store URL
            _start_process_monitor(game_id, proc, fallback_cmd=launch_cmd)
            logger.info(f"Direct launch: {game['name']}")
            return jsonify({'status': 'launched', 'game': game['name'], 'mode': 'direct'})

        if launch_cmd.startswith(('steam://', 'com.epicgames.launcher://',
                                   'goggalaxy://', 'uplay://', 'battlenet://',
                                   'link2ea://', 'origin://', 'shell:')):
            # URL protocol launch
            os.startfile(launch_cmd)
            _set_active(None, game_id)
            # Monitor via polling (URL launches are fire-and-forget)
            _start_url_monitor(game_id)
        else:
            # Direct executable launch (local games, ROMs, GOG with registry exe)
            args = shlex.split(launch_cmd)
            proc = subprocess.Popen(
                args,
                shell=False,
                cwd=game.get('install_dir', None) or None,
            )
            _set_active(proc, game_id)
            # Monitor process in background
            _start_process_monitor(game_id, proc)

        return jsonify({'status': 'launched', 'game': game['name'], 'mode': 'store'})
    except Exception as e:
        logger.error(f"Launch failed: {e}")
        userdata.session_end(game_id)
        return jsonify({'error': str(e)}), 500


def _start_process_monitor(game_id, proc, fallback_cmd=None):
    """Monitor a subprocess and end session when it exits.

    If fallback_cmd is set and the process dies within 5 seconds (likely DRM
    rejection), automatically retry via the store protocol URL.
    """
    start_time = time.time()

    def monitor():
        proc.wait()
        elapsed = time.time() - start_time

        # If process died very quickly and we have a fallback, retry via store
        if fallback_cmd and elapsed < 5.0 and proc.returncode != 0:
            logger.warning(f"Direct launch failed in {elapsed:.1f}s (exit={proc.returncode}), "
                           f"falling back to store URL for {game_id}")
            try:
                if fallback_cmd.startswith(('steam://', 'com.epicgames.launcher://',
                                            'goggalaxy://', 'uplay://', 'battlenet://',
                                            'link2ea://', 'origin://', 'shell:')):
                    os.startfile(fallback_cmd)
                    _set_active(None, game_id)
                    _start_url_monitor(game_id)
                    return
            except Exception as e:
                logger.error(f"Fallback launch also failed: {e}")

        userdata.session_end(game_id)
        _clear_active(game_id)
        logger.info(f"Game exited: {game_id}")

    t = threading.Thread(target=monitor, daemon=True)
    t.start()


def _start_url_monitor(game_id):
    """Monitor a URL-launched game using process-snapshot diffing.

    Strategy: snapshot PIDs before launch, wait for new processes to appear,
    then monitor those new PIDs until they all exit. Falls back to a 2-hour
    timeout if no new processes are detected.
    """
    import psutil

    # Snapshot current PIDs before the game has time to start
    pre_pids = set(psutil.pids())

    def monitor():
        # Wait for the store launcher to start the game
        time.sleep(15)

        _, current_game_id = _get_active()
        if current_game_id != game_id:
            return  # Already cleared by another path

        # Find new processes that appeared since launch
        post_pids = set(psutil.pids())
        new_pids = post_pids - pre_pids

        # Filter to likely game processes (exclude tiny/system processes)
        game_pids = set()
        for pid in new_pids:
            try:
                p = psutil.Process(pid)
                # Skip known non-game processes
                name = p.name().lower()
                if name in ('conhost.exe', 'dllhost.exe', 'svchost.exe',
                            'runtimebroker.exe', 'backgroundtaskhost.exe',
                            'searchprotocolhost.exe', 'smartscreen.exe'):
                    continue
                # Include processes using meaningful memory (>50MB)
                mem = p.memory_info().rss
                if mem > 50 * 1024 * 1024:
                    game_pids.add(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not game_pids:
            # No clear game process found — use fixed timeout (30 min default)
            logger.info(f"URL monitor: no new large process for {game_id}, "
                        f"will timeout after 30 min")
            time.sleep(1800)
            _, cid = _get_active()
            if cid == game_id:
                userdata.session_end(game_id)
                _clear_active(game_id)
                logger.info(f"URL-launched game timed out: {game_id}")
            return

        logger.info(f"URL monitor: tracking {len(game_pids)} new process(es) "
                     f"for {game_id}")

        # Monitor tracked PIDs until they all exit (max 8 hours)
        max_checks = 2880  # 8h at 10s intervals
        for _ in range(max_checks):
            time.sleep(10)
            _, cid = _get_active()
            if cid != game_id:
                return  # Session ended by another path (e.g., manual /api/session/end)

            alive = False
            for pid in game_pids:
                try:
                    p = psutil.Process(pid)
                    if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                        alive = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if not alive:
                userdata.session_end(game_id)
                _clear_active(game_id)
                logger.info(f"URL-launched game exited: {game_id}")
                return

        # Max time reached
        userdata.session_end(game_id)
        _clear_active(game_id)
        logger.info(f"URL monitor max time reached for: {game_id}")

    t = threading.Thread(target=monitor, daemon=True)
    t.start()


@app.route('/api/session/end/<game_id>', methods=['POST'])
def api_session_end(game_id):
    userdata.session_end(game_id)
    _clear_active(game_id)
    logger.info(f"Session ended via API: {game_id}")
    return jsonify({'status': 'ok'})


@app.route('/api/rescan', methods=['POST'])
def api_rescan():
    def do_scan():
        _build_library()
    threading.Thread(target=do_scan, daemon=True).start()
    return jsonify({'status': 'scanning'})


# ── Search ──────────────────────────────────────────────────────────────────

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify([])

    favorites = set(userdata.get_favorites())
    with _library_lock:
        snapshot = list(game_library)

    results = []
    for game in snapshot:
        if query in game['name'].lower():
            enriched = dict(game)
            enriched['is_favorite'] = game['id'] in favorites
            results.append(enriched)

    # Sort: exact start matches first, then alphabetical
    results.sort(key=lambda g: (0 if g['name'].lower().startswith(query) else 1, g['name'].lower()))
    return jsonify(results[:50])


# ── Play Time ───────────────────────────────────────────────────────────────

@app.route('/api/playtime')
def api_playtime():
    return jsonify(userdata.get_playtime())


# ── Collections ─────────────────────────────────────────────────────────────

@app.route('/api/collections', methods=['GET'])
def api_get_collections():
    return jsonify(userdata.get_collections())


@app.route('/api/collections', methods=['POST'])
def api_create_collection():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    if userdata.create_collection(name):
        return jsonify({'status': 'created', 'name': name})
    return jsonify({'error': 'Already exists'}), 409


@app.route('/api/collections/<name>', methods=['DELETE'])
def api_delete_collection(name):
    if userdata.delete_collection(name):
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/collections/<name>/games', methods=['POST'])
def api_add_to_collection(name):
    data = request.get_json() or {}
    game_id = data.get('game_id', '')
    if userdata.add_to_collection(name, game_id):
        return jsonify({'status': 'added'})
    return jsonify({'error': 'Collection not found'}), 404


@app.route('/api/collections/<name>/games/<game_id>', methods=['DELETE'])
def api_remove_from_collection(name, game_id):
    if userdata.remove_from_collection(name, game_id):
        return jsonify({'status': 'removed'})
    return jsonify({'error': 'Not found'}), 404


# ── Favorites ───────────────────────────────────────────────────────────────

@app.route('/api/favorites')
def api_favorites():
    return jsonify(userdata.get_favorites())


@app.route('/api/favorites/toggle', methods=['POST'])
def api_toggle_favorite():
    data = request.get_json() or {}
    game_id = data.get('game_id', '')
    is_fav = userdata.toggle_favorite(game_id)
    return jsonify({'game_id': game_id, 'is_favorite': is_fav})


# ── Hidden Systems ──────────────────────────────────────────────────────────

@app.route('/api/hidden-systems')
def api_hidden_systems():
    return jsonify(userdata.get_hidden_systems())


@app.route('/api/hidden-systems/toggle', methods=['POST'])
def api_toggle_hidden_system():
    data = request.get_json() or {}
    system = data.get('system', '')
    is_hidden = userdata.toggle_hidden_system(system)
    return jsonify({'system': system, 'is_hidden': is_hidden})


# ── Stores & Directories ───────────────────────────────────────────────────

@app.route('/api/stores')
def api_stores():
    return jsonify(scanner.get_detected_stores())


@app.route('/api/local-dirs', methods=['GET'])
def api_get_local_dirs():
    return jsonify(userdata.get_local_dirs())


@app.route('/api/local-dirs', methods=['POST'])
def api_add_local_dir():
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'error': 'Path required'}), 400
    err = _validate_dir_path(path)
    if err:
        return jsonify({'error': err}), 400
    return jsonify(userdata.add_local_dir(path))


@app.route('/api/local-dirs', methods=['DELETE'])
def api_remove_local_dir():
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    return jsonify(userdata.remove_local_dir(path))


@app.route('/api/rom-dirs', methods=['GET'])
def api_get_rom_dirs():
    return jsonify(userdata.get_rom_dirs())


@app.route('/api/rom-dirs', methods=['POST'])
def api_add_rom_dir():
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'error': 'Path required'}), 400
    err = _validate_dir_path(path)
    if err:
        return jsonify({'error': err}), 400
    dirs = userdata.add_rom_dir(path)
    # Trigger rescan
    threading.Thread(target=_build_library, daemon=True).start()
    return jsonify(dirs)


@app.route('/api/rom-dirs', methods=['DELETE'])
def api_remove_rom_dir():
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    dirs = userdata.remove_rom_dir(path)
    threading.Thread(target=_build_library, daemon=True).start()
    return jsonify(dirs)


# ── Accounts ────────────────────────────────────────────────────────────────

@app.route('/api/accounts')
def api_accounts():
    """Get connected account status."""
    accounts = userdata.get_accounts()

    # Check GOG Galaxy availability
    galaxy_db = GogGalaxyDB()
    galaxy_available = galaxy_db.is_available()
    galaxy_platforms = galaxy_db.get_connected_platforms() if galaxy_available else []

    # Check Epic catalog availability
    epic_catalog = EpicCatalogDB()

    # Auto-detect Steam users from local files
    detected_steam = detect_steam_users()

    return jsonify({
        'steam': {
            'connected': accounts.get('steam', {}).get('connected', False),
            'persona_name': accounts.get('steam', {}).get('persona_name', ''),
            'steam_id': accounts.get('steam', {}).get('steam_id', ''),
            'has_api_key': bool(accounts.get('steam', {}).get('api_key', '')),
            'detected_users': detected_steam,
        },
        'gog_galaxy': {
            'available': galaxy_available,
            'enabled': accounts.get('gog_galaxy', {}).get('enabled', False),
            'connected_platforms': galaxy_platforms,
        },
        'epic': {
            'launcher_installed': epic_catalog.is_launcher_installed(),
            'catalog_available': epic_catalog.is_available(),
            'legendary_installed': EpicAccount.is_available(),
            'authenticated': EpicAccount.is_authenticated(),
        },
    })


@app.route('/api/accounts/steam/connect', methods=['POST'])
def api_connect_steam():
    """Connect a Steam account.

    Two modes:
    - Quick connect (steam_id only): uses auto-detected Steam ID from local
      files. Installed games are already scanned; this saves the persona name.
    - Full connect (steam_id + api_key): also fetches ALL owned games
      (including uninstalled) via Steam Web API.
    """
    data = request.get_json() or {}
    api_key = data.get('api_key', '').strip()
    steam_id = data.get('steam_id', '').strip()

    if not steam_id:
        return jsonify({'error': 'Steam ID required'}), 400

    # Handle various Steam ID formats
    if 'steamcommunity.com' in steam_id:
        if '/id/' in steam_id:
            vanity = steam_id.split('/id/')[-1].strip('/')
            if api_key:
                resolved = resolve_steam_vanity_url(api_key, vanity)
                if not resolved:
                    return jsonify({'error': f'Could not resolve vanity URL: {vanity}'}), 400
                steam_id = resolved
            else:
                return jsonify({'error': 'API key needed to resolve vanity URLs'}), 400
        elif '/profiles/' in steam_id:
            steam_id = steam_id.split('/profiles/')[-1].strip('/')

    if not steam_id.isdigit():
        if api_key:
            resolved = resolve_steam_vanity_url(api_key, steam_id)
            if not resolved:
                return jsonify({'error': f'Could not resolve: {steam_id}'}), 400
            steam_id = resolved
        else:
            return jsonify({'error': 'API key needed to resolve vanity names'}), 400

    # If API key provided, validate it
    persona_name = ''
    if api_key:
        steam = SteamAccount(api_key, steam_id)
        validation = steam.validate()
        if not validation['valid']:
            return jsonify({'error': validation['error']}), 400
        persona_name = validation.get('persona_name', '')
    else:
        # Try to get persona name from local detection
        detected = detect_steam_users()
        for user in detected:
            if user['steam_id'] == steam_id:
                persona_name = user['persona_name']
                break

    # Save account
    userdata.set_steam_account(api_key, steam_id, persona_name)

    # Trigger library rescan
    threading.Thread(target=_build_library, daemon=True).start()

    return jsonify({
        'status': 'connected',
        'persona_name': persona_name,
        'has_api_key': bool(api_key),
    })


@app.route('/api/accounts/steam/disconnect', methods=['POST'])
def api_disconnect_steam():
    """Disconnect the Steam account."""
    userdata.disconnect_steam_account()
    threading.Thread(target=_build_library, daemon=True).start()
    return jsonify({'status': 'disconnected'})


@app.route('/api/accounts/gog-galaxy/toggle', methods=['POST'])
def api_toggle_gog_galaxy():
    """Enable or disable GOG Galaxy database integration."""
    galaxy_config = userdata.get_gog_galaxy_config()
    galaxy_db = GogGalaxyDB()

    if not galaxy_db.is_available():
        return jsonify({'error': 'GOG Galaxy not found on this system'}), 404

    new_state = not galaxy_config.get('enabled', False)
    userdata.set_gog_galaxy_enabled(new_state, str(galaxy_db.db_path))

    # Trigger library rescan
    threading.Thread(target=_build_library, daemon=True).start()

    return jsonify({
        'enabled': new_state,
        'platforms': galaxy_db.get_connected_platforms() if new_state else [],
    })


@app.route('/api/accounts/epic/auth', methods=['POST'])
def api_epic_auth():
    """Start Epic auth flow via legendary (opens browser)."""
    result = EpicAccount.start_auth()
    if result['status'] == 'ok':
        threading.Thread(target=_build_library, daemon=True).start()
    return jsonify(result)


@app.route('/api/settings/show-uninstalled', methods=['GET'])
def api_get_show_uninstalled():
    """Get current show_uninstalled setting."""
    settings = userdata.get_settings()
    return jsonify({'show_uninstalled': settings.get('show_uninstalled', True)})


@app.route('/api/settings/show-uninstalled', methods=['POST'])
def api_toggle_show_uninstalled():
    """Toggle showing uninstalled games from connected accounts."""
    settings = userdata.get_settings()
    new_val = not settings.get('show_uninstalled', True)
    userdata.update_settings({'show_uninstalled': new_val})
    threading.Thread(target=_build_library, daemon=True).start()
    return jsonify({'show_uninstalled': new_val})


@app.route('/api/settings/direct-launch', methods=['GET'])
def api_get_direct_launch():
    """Get current direct_launch setting."""
    settings = userdata.get_settings()
    return jsonify({'direct_launch': settings.get('direct_launch', True)})


@app.route('/api/settings/direct-launch', methods=['POST'])
def api_toggle_direct_launch():
    """Toggle direct game launching (bypass store clients when possible)."""
    settings = userdata.get_settings()
    new_val = not settings.get('direct_launch', True)
    userdata.update_settings({'direct_launch': new_val})
    return jsonify({'direct_launch': new_val})


@app.route('/api/settings/start-in-game-mode', methods=['GET'])
def api_get_start_in_game_mode():
    """Get start_in_game_mode setting."""
    settings = userdata.get_settings()
    return jsonify({'start_in_game_mode': settings.get('start_in_game_mode', False)})


@app.route('/api/settings/start-in-game-mode', methods=['POST'])
def api_toggle_start_in_game_mode():
    """Toggle start in game mode."""
    settings = userdata.get_settings()
    new_val = not settings.get('start_in_game_mode', False)
    userdata.update_settings({'start_in_game_mode': new_val})
    return jsonify({'start_in_game_mode': new_val})


@app.route('/api/settings/direct-launch/<game_id>', methods=['GET'])
def api_get_game_direct_launch(game_id):
    """Get per-game direct launch override."""
    override = userdata.get_direct_launch_override(game_id)
    global_val = userdata.get_settings().get('direct_launch', True)
    return jsonify({
        'override': override,           # True/False/null
        'effective': override if override is not None else global_val,
    })


@app.route('/api/settings/direct-launch/<game_id>', methods=['POST'])
def api_set_game_direct_launch(game_id):
    """Cycle per-game direct launch: global default → force on → force off → global default."""
    data = request.get_json(silent=True) or {}
    value = data.get('value')  # True, False, or null/missing → remove override
    if value is None:
        userdata.set_direct_launch_override(game_id, None)
    else:
        userdata.set_direct_launch_override(game_id, bool(value))
    override = userdata.get_direct_launch_override(game_id)
    global_val = userdata.get_settings().get('direct_launch', True)
    return jsonify({
        'override': override,
        'effective': override if override is not None else global_val,
    })


# ── RetroArch Path ─────────────────────────────────────────────────────────

@app.route('/api/settings/retroarch-path', methods=['GET'])
def api_get_retroarch_path():
    settings = userdata.get_settings()
    return jsonify({'retroarch_path': settings.get('retroarch_path', '')})


@app.route('/api/settings/retroarch-path', methods=['POST'])
def api_set_retroarch_path():
    data = request.get_json(silent=True) or {}
    path = data.get('path', '').strip()
    if path and not Path(path).exists():
        return jsonify({'error': 'File not found'}), 400
    userdata.update_settings({'retroarch_path': path})
    # Update scanner — it expects the RetroArch directory (containing retroarch.exe)
    if path:
        p = Path(path)
        scanner._retroarch_path = p.parent if p.is_file() else p
    else:
        scanner._retroarch_path = None
    return jsonify({'retroarch_path': path})


# ── Artwork Progress ───────────────────────────────────────────────────────

@app.route('/api/artwork/progress')
def api_artwork_progress():
    return jsonify(artwork_scraper.batch_progress)


# ── Settings Test Endpoints ────────────────────────────────────────────────

@app.route('/api/test/retroarch', methods=['POST'])
def api_test_retroarch():
    data = request.get_json(silent=True) or {}
    ra_path = data.get('path', '').strip()
    if not ra_path or not Path(ra_path).exists():
        return jsonify({'ok': False, 'message': 'File not found'})
    try:
        result = subprocess.run(
            [ra_path, '--version'],
            capture_output=True, text=True, timeout=5,
        )
        version = (result.stdout + result.stderr).strip()
        if version:
            return jsonify({'ok': True, 'message': version[:200]})
        return jsonify({'ok': True, 'message': 'RetroArch found (no version info)'})
    except subprocess.TimeoutExpired:
        return jsonify({'ok': True, 'message': 'RetroArch found (timed out reading version)'})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)[:200]})


@app.route('/api/test/launchbox', methods=['POST'])
def api_test_launchbox():
    data = request.get_json(silent=True) or {}
    lb_path = data.get('path', '').strip()
    if not lb_path or not Path(lb_path).is_dir():
        return jsonify({'ok': False, 'message': 'Directory not found'})

    images_dir = Path(lb_path) / 'Images'
    data_dir = Path(lb_path) / 'Data' / 'Platforms'

    results = {}
    if images_dir.is_dir():
        platforms = [d.name for d in images_dir.iterdir() if d.is_dir() and not d.name.startswith('Cache')]
        results['image_platforms'] = len(platforms)
    else:
        results['image_platforms'] = 0

    if data_dir.is_dir():
        xml_count = len(list(data_dir.glob('*.xml')))
        results['data_files'] = xml_count
    else:
        results['data_files'] = 0

    results['title_index'] = len(artwork_scraper._lb_title_index)
    results['ok'] = results['image_platforms'] > 0 or results['data_files'] > 0

    if results['ok']:
        msg = f"{results['image_platforms']} platforms with artwork, {results['title_index']} games indexed"
    else:
        msg = 'No Images/ or Data/Platforms/ found — check the path'
    results['message'] = msg
    return jsonify(results)


# ── LaunchBox Artwork ──────────────────────────────────────────────────────

@app.route('/api/settings/launchbox-path', methods=['GET'])
def api_get_launchbox_path():
    settings = userdata.get_settings()
    return jsonify({'launchbox_path': settings.get('launchbox_path', '')})


@app.route('/api/settings/launchbox-path', methods=['POST'])
def api_set_launchbox_path():
    data = request.get_json(silent=True) or {}
    path = data.get('path', '').strip()
    if path and not Path(path).is_dir():
        return jsonify({'error': 'Directory not found'}), 400
    userdata.update_settings({'launchbox_path': path})
    artwork_scraper.set_launchbox_path(path)
    # Also refresh emulator discovery from LaunchBox
    if path:
        lb_root = artwork_scraper._resolve_lb_root(path)
        if lb_root:
            scanner._lb_emulators = discover_launchbox_emulators(str(lb_root))
    matched_count = len(artwork_scraper._lb_title_index) if path else 0
    return jsonify({'launchbox_path': path, 'matched_count': matched_count})


# ── CatByte AI ──────────────────────────────────────────────────────────────

@app.route('/api/catbyte/status')
def api_catbyte_status():
    return jsonify(catbyte.check_status())


@app.route('/api/catbyte/config', methods=['GET'])
def api_catbyte_config():
    """Get CatByte config (safe — no API key exposed)."""
    return jsonify(catbyte.get_config())


@app.route('/api/catbyte/config', methods=['POST'])
def api_catbyte_config_update():
    """Update CatByte backend configuration."""
    data = request.get_json() or {}
    allowed_keys = {'backend', 'base_url', 'api_key', 'model',
                    'cat_puns', 'game_awareness'}
    updates = {k: v for k, v in data.items() if k in allowed_keys}
    if updates:
        userdata.update_catbyte_config(updates)
        catbyte.configure(userdata.get_catbyte_config())
    return jsonify(catbyte.get_config())


@app.route('/api/catbyte/presets')
def api_catbyte_presets():
    """Get available backend presets for settings UI."""
    return jsonify(catbyte.get_presets())


@app.route('/api/catbyte/models')
def api_catbyte_models():
    """List models available on the configured backend."""
    return jsonify(catbyte.list_models())


@app.route('/api/catbyte/test', methods=['POST'])
def api_catbyte_test():
    """Test the current backend connection end-to-end."""
    return jsonify(catbyte.test_connection())


@app.route('/api/catbyte/openclaw-info')
def api_catbyte_openclaw_info():
    """Get OpenClaw routing info: primary model and available models."""
    return jsonify(catbyte.get_openclaw_info())


@app.route('/api/catbyte/sessions', methods=['GET'])
def api_catbyte_sessions():
    """List all chat sessions (summaries, no messages)."""
    sessions = chat_history.list_sessions()
    active_id = chat_history.get_active_session_id()
    return jsonify({'sessions': sessions, 'active_session_id': active_id})


@app.route('/api/catbyte/sessions', methods=['POST'])
def api_catbyte_session_create():
    """Create a new chat session."""
    data = request.get_json() or {}
    game_context = data.get('game_context', '')
    model = data.get('model', catbyte.get_model())
    if not game_context:
        _, current_game_id = _get_active()
        if current_game_id:
            with _library_lock:
                game = game_index.get(current_game_id, {})
            game_context = game.get('name', '')
    session = chat_history.create_session(game_context=game_context, model=model)
    return jsonify(session)


@app.route('/api/catbyte/sessions/<session_id>', methods=['GET'])
def api_catbyte_session_get(session_id):
    """Get a full chat session with all messages."""
    session = chat_history.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify(session)


@app.route('/api/catbyte/sessions/<session_id>', methods=['DELETE'])
def api_catbyte_session_delete(session_id):
    """Delete a chat session."""
    if chat_history.delete_session(session_id):
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Session not found'}), 404


@app.route('/api/catbyte/sessions/<session_id>', methods=['PATCH'])
def api_catbyte_session_update(session_id):
    """Rename or toggle pin on a session."""
    data = request.get_json() or {}
    if 'title' in data:
        chat_history.rename_session(session_id, data['title'])
    if 'pinned' in data:
        chat_history.toggle_pin(session_id)
    session = chat_history.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify(session)


@app.route('/api/catbyte/sessions/<session_id>/active', methods=['POST'])
def api_catbyte_session_set_active(session_id):
    """Set a session as the active one."""
    chat_history.set_active_session(session_id)
    return jsonify({'status': 'ok'})


@app.route('/api/catbyte/chat', methods=['POST'])
def api_catbyte_chat():
    data = request.get_json() or {}
    message = data.get('message', '')
    session_id = data.get('session_id', '')
    game_context = data.get('game_context', '')

    if not message:
        return jsonify({'error': 'Message required'}), 400

    # Auto-detect game context from active game
    if not game_context:
        _, current_game_id = _get_active()
        if current_game_id:
            with _library_lock:
                game = game_index.get(current_game_id, {})
            game_context = game.get('name', '')

    # Session-based: persist messages and load history from session
    history = []
    if session_id:
        chat_history.add_message(session_id, 'user', message)
        history = chat_history.get_messages_for_llm(session_id, limit=20)
        # Remove last message (it's the current one, sent separately)
        history = history[:-1]

    result = catbyte.chat(message, game_context=game_context, history=history)

    if session_id and result.get('status') != 'offline':
        chat_history.add_message(session_id, 'assistant', result.get('response', ''))
        # Auto-generate title after first exchange
        session = chat_history.get_session(session_id)
        if session and len(session.get('messages', [])) == 2:
            _auto_title_session(session_id, session.get('messages', []))

    return jsonify({**result, 'session_id': session_id})


@app.route('/api/catbyte/chat-vision', methods=['POST'])
def api_catbyte_chat_vision():
    data = request.get_json() or {}
    message = data.get('message', '')
    image = data.get('image', '')
    session_id = data.get('session_id', '')
    game_context = data.get('game_context', '')

    if not message or not image:
        return jsonify({'error': 'Message and image required'}), 400

    if not game_context:
        _, current_game_id = _get_active()
        if current_game_id:
            with _library_lock:
                game = game_index.get(current_game_id, {})
            game_context = game.get('name', '')

    history = []
    if session_id:
        chat_history.add_message(session_id, 'user', message)
        history = chat_history.get_messages_for_llm(session_id, limit=10)
        history = history[:-1]

    result = catbyte.chat_vision(message, image, game_context=game_context, history=history)

    if session_id and result.get('status') != 'offline':
        chat_history.add_message(session_id, 'assistant', result.get('response', ''))

    return jsonify({**result, 'session_id': session_id})


def _auto_title_session(session_id: str, messages: list):
    """Generate a title for a new session in a background thread."""
    def _generate():
        try:
            title_result = catbyte.generate_title(messages)
            title = title_result.get('title', '').strip()
            if title and len(title) < 80:
                chat_history.rename_session(session_id, title)
                logger.info(f"Auto-titled session {session_id}: {title}")
        except Exception as e:
            logger.warning(f"Auto-title failed for {session_id}: {e}")

    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()


# ── Metadata ────────────────────────────────────────────────────────────────

# ── BIOS Management ────────────────────────────────────────────────────────

@app.route('/api/bios/status')
def api_bios_status():
    """Get per-system BIOS file status."""
    return jsonify(bios_manager.get_status())


@app.route('/api/bios/dirs', methods=['GET'])
def api_get_bios_dirs():
    return jsonify(bios_manager.get_bios_dirs())


@app.route('/api/bios/dirs', methods=['POST'])
def api_add_bios_dir():
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'error': 'Path required'}), 400
    err = _validate_dir_path(path)
    if err:
        return jsonify({'error': err}), 400

    settings = userdata.get_settings()
    bios_dirs = settings.get('bios_dirs', [])
    if path not in bios_dirs:
        bios_dirs.append(path)
        userdata.update_settings({'bios_dirs': bios_dirs})
        bios_manager.set_bios_dirs(bios_dirs)

    return jsonify(bios_manager.get_status())


@app.route('/api/bios/dirs', methods=['DELETE'])
def api_remove_bios_dir():
    data = request.get_json() or {}
    path = data.get('path', '').strip()

    settings = userdata.get_settings()
    bios_dirs = settings.get('bios_dirs', [])
    if path in bios_dirs:
        bios_dirs.remove(path)
        userdata.update_settings({'bios_dirs': bios_dirs})
        bios_manager.set_bios_dirs(bios_dirs)

    return jsonify(bios_manager.get_status())


# ── Emulator Auto-Setup ────────────────────────────────────────────────────

@app.route('/api/emulators/status')
def api_emulators_status():
    """Get install status for all emulators needed by the user's ROM library."""
    with _library_lock:
        rom_systems = list({
            g['system'] for g in game_library
            if g.get('source') == 'retro' and g.get('system')
        })
    return jsonify(emu_setup.get_status(rom_systems))


@app.route('/api/emulators/setup', methods=['POST'])
def api_emulators_setup():
    """Trigger auto-download of RetroArch + needed cores."""
    if emu_setup.progress.get('active'):
        return jsonify({'error': 'Setup already in progress'}), 409

    with _library_lock:
        rom_systems = {
            g['system'] for g in game_library
            if g.get('source') == 'retro' and g.get('system')
        }
    needed_cores = emu_setup.get_needed_cores(rom_systems)

    def run():
        emu_setup.setup(needed_cores)
        # Point scanner to the managed RetroArch and rescan library
        managed = emu_setup.get_retroarch_path()
        if managed:
            scanner._retroarch_path = managed
        try:
            _build_library()
        except Exception as e:
            logger.error(f"Post-setup rescan failed: {e}")

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'cores': len(needed_cores)})


@app.route('/api/emulators/progress')
def api_emulators_progress():
    """Get current emulator setup progress."""
    return jsonify(emu_setup.progress)


# ── Built-in Emulator ───────────────────────────────────────────────────────

@app.route('/api/rom/<game_id>')
def api_serve_rom(game_id):
    """Serve a ROM file for the built-in emulator."""
    with _library_lock:
        game = game_index.get(game_id)
    if not game:
        abort(404)

    rom_path = game.get('file_path', '')
    if not rom_path or not Path(rom_path).exists():
        abort(404)

    # Validate resolved path is within configured ROM directories
    rom_dirs = userdata.get_rom_dirs()
    if not _validate_file_within_dirs(rom_path, rom_dirs):
        logger.warning(f"ROM path outside allowed dirs: {rom_path}")
        abort(403)

    try:
        return send_file(
            rom_path,
            mimetype='application/octet-stream',
            as_attachment=False,
            download_name=Path(rom_path).name,
        )
    except FileNotFoundError:
        abort(404)


@app.route('/api/bios/<system>')
@app.route('/api/bios/<system>/<filename>')
def api_serve_bios(system, filename=None):
    """Serve BIOS files for the built-in emulator."""
    bios_path = bios_manager.get_bios_path(system, filename)
    if not bios_path or not Path(bios_path).exists():
        abort(404)

    # Validate resolved path is within configured BIOS directories or built-in bios/
    bios_dirs = userdata.get_settings().get('bios_dirs', [])
    builtin_bios = str(Path(__file__).parent / 'bios')
    if not _validate_file_within_dirs(bios_path, bios_dirs + [builtin_bios]):
        logger.warning(f"BIOS path outside allowed dirs: {bios_path}")
        abort(403)

    try:
        return send_file(bios_path, mimetype='application/octet-stream')
    except FileNotFoundError:
        abort(404)


# ── Directory Validation ───────────────────────────────────────────────────

@app.route('/api/validate-path', methods=['POST'])
def api_validate_path():
    """Check if a path exists and what it contains."""
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'valid': False, 'message': 'No path provided'})

    p = Path(path)
    if not p.exists():
        return jsonify({'valid': False, 'message': 'Path does not exist'})
    if not p.is_dir():
        return jsonify({'valid': False, 'message': 'Path is not a directory'})

    # Count contents for preview
    try:
        files = list(p.iterdir())
        dirs = [f for f in files if f.is_dir()]
        regular_files = [f for f in files if f.is_file()]
        return jsonify({
            'valid': True,
            'message': f'{len(dirs)} folders, {len(regular_files)} files',
            'dirs': len(dirs),
            'files': len(regular_files),
        })
    except PermissionError:
        return jsonify({'valid': False, 'message': 'Permission denied'})


@app.route('/api/scan-rom-dir', methods=['POST'])
def api_scan_rom_dir():
    """Preview what ROMs would be found in a directory."""
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    if not path or not Path(path).is_dir():
        return jsonify({'error': 'Invalid directory'}), 400

    # Quick scan for ROM-like files by extension
    rom_exts = {
        '.nes': 'NES', '.sfc': 'SNES', '.smc': 'SNES',
        '.gba': 'GBA', '.gb': 'GB', '.gbc': 'GBC',
        '.n64': 'N64', '.z64': 'N64', '.v64': 'N64',
        '.nds': 'NDS', '.bin': 'PS1/Genesis',
        '.cue': 'PS1', '.iso': 'PS1/PS2/PSP',
        '.chd': 'PS1/PS2', '.pbp': 'PSP',
        '.md': 'Genesis', '.gen': 'Genesis',
        '.sms': 'Master System', '.gg': 'Game Gear',
        '.a26': 'Atari 2600', '.zip': 'Arcade/Various',
    }
    systems = {}
    try:
        for item in Path(path).rglob('*'):
            if item.is_file():
                ext = item.suffix.lower()
                if ext in rom_exts:
                    sys_name = rom_exts[ext]
                    systems[sys_name] = systems.get(sys_name, 0) + 1
    except PermissionError:
        pass

    total = sum(systems.values())
    return jsonify({
        'total': total,
        'systems': systems,
    })


@app.route('/api/epic/manifest-count')
def api_epic_manifest_count():
    """Count Epic games: installed (manifests) + owned (catalog cache)."""
    epic_catalog = EpicCatalogDB()
    launcher_installed = epic_catalog.is_launcher_installed()

    # Installed games from manifests
    manifest_dir = epic_catalog.LAUNCHER_DIR / 'Data' / 'Manifests'
    installed_count = 0
    installed_games = []
    if manifest_dir.exists():
        for item_file in manifest_dir.glob('*.item'):
            try:
                with open(item_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                name = data.get('DisplayName', '')
                install_loc = data.get('InstallLocation', '')
                if name and install_loc and Path(install_loc).exists():
                    installed_count += 1
                    installed_games.append(name)
            except Exception as e:
                logger.debug(f"Failed to read Epic manifest {item_file}: {e}")

    # Owned games from catalog cache
    owned_count = 0
    if epic_catalog.is_available():
        try:
            owned_games = epic_catalog.get_all_games()
            owned_count = len(owned_games)
        except Exception as e:
            logger.error(f"Epic catalog read failed: {e}")

    return jsonify({
        'count': installed_count,
        'owned_count': owned_count,
        'games': installed_games[:10],
        'launcher_installed': launcher_installed,
        'catalog_available': epic_catalog.is_available(),
    })


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=FLASK_PORT, debug=False, threaded=True)
