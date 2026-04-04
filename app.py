"""
YancoHub — Flask Backend
Unified game launcher for Windows with CatByte AI companion.
"""

import os
import sys
import json
import time
import logging
import shlex
import subprocess
import threading
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_file, abort

from scanner import GameScanner
from userdata import UserData
from catbyte import CatByte
from accounts import SteamAccount, GogGalaxyDB, EpicAccount, resolve_steam_vanity_url
from metadata import MetadataFetcher
from artwork import ArtworkScraper
from biosmanager import BIOSManager

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
catbyte = CatByte()
metadata_fetcher = MetadataFetcher()
artwork_scraper = ArtworkScraper()
bios_manager = BIOSManager()

# Initialize BIOS dirs from settings
_bios_dirs = userdata.get_settings().get('bios_dirs', [])
if _bios_dirs:
    bios_manager.set_bios_dirs(_bios_dirs)

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

    # 3. Epic via legendary
    if EpicAccount.is_authenticated():
        try:
            epic_games = EpicAccount.get_owned_games()
            account_games.extend(epic_games)
            logger.info(f"Epic account: {len(epic_games)} owned games")
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

    # Background: enrich metadata and fetch artwork for new games
    def _enrich():
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
    with _library_lock:
        game = game_index.get(game_id)
    if not game:
        abort(404)

    def _send_artwork(path: str):
        """Send an artwork file with cache headers."""
        resp = send_file(path)
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp

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
        if launch_cmd.startswith(('steam://', 'com.epicgames.launcher://',
                                   'goggalaxy://', 'uplay://', 'battlenet://',
                                   'link2ea://', 'origin://', 'shell:')):
            # URL protocol launch
            os.startfile(launch_cmd)
            _set_active(None, game_id)
            # Monitor via polling (URL launches are fire-and-forget)
            _start_url_monitor(game_id)
        else:
            # Direct executable launch
            args = shlex.split(launch_cmd)
            proc = subprocess.Popen(
                args,
                shell=False,
                cwd=game.get('install_dir', None) or None,
            )
            _set_active(proc, game_id)
            # Monitor process in background
            _start_process_monitor(game_id, proc)

        return jsonify({'status': 'launched', 'game': game['name']})
    except Exception as e:
        logger.error(f"Launch failed: {e}")
        userdata.session_end(game_id)
        return jsonify({'error': str(e)}), 500


def _start_process_monitor(game_id, proc):
    """Monitor a subprocess and end session when it exits."""
    def monitor():
        proc.wait()
        userdata.session_end(game_id)
        _clear_active(game_id)
        logger.info(f"Game exited: {game_id}")

    t = threading.Thread(target=monitor, daemon=True)
    t.start()


def _start_url_monitor(game_id):
    """Monitor a URL-launched game by checking if its process is still running."""
    def monitor():
        import psutil
        # Wait for game to start
        time.sleep(10)
        with _library_lock:
            game = game_index.get(game_id, {})
        game_name = game.get('name', '').lower()

        # Poll for game process
        max_checks = 720  # 2 hours max
        for _ in range(max_checks):
            time.sleep(10)
            # Check if any process matches the game name
            found = False
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    pname = proc.info.get('name', '').lower()
                    if any(word in pname for word in game_name.split()[:2] if len(word) > 3):
                        found = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            _, current_game_id = _get_active()
            if not found and current_game_id == game_id:
                # Game seems to have exited
                userdata.session_end(game_id)
                _clear_active(game_id)
                logger.info(f"URL-launched game exited: {game_id}")
                return

    t = threading.Thread(target=monitor, daemon=True)
    t.start()


@app.route('/api/active-game')
def api_active_game():
    _, current_game_id = _get_active()
    if current_game_id:
        with _library_lock:
            game = game_index.get(current_game_id, {})
        return jsonify({
            'game_id': current_game_id,
            'name': game.get('name', ''),
            'source': game.get('source', ''),
            'system': game.get('system', ''),
        })
    return jsonify(None)


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


@app.route('/api/last-played')
def api_last_played():
    return jsonify({'game_id': userdata.get_last_played()})


# ── Collections ─────────────────────────────────────────────────────────────

@app.route('/api/collections', methods=['GET'])
def api_get_collections():
    return jsonify(userdata.get_collections())


@app.route('/api/collections', methods=['POST'])
def api_create_collection():
    data = request.get_json()
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
    data = request.get_json()
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
    data = request.get_json()
    game_id = data.get('game_id', '')
    is_fav = userdata.toggle_favorite(game_id)
    return jsonify({'game_id': game_id, 'is_favorite': is_fav})


# ── Hidden Systems ──────────────────────────────────────────────────────────

@app.route('/api/hidden-systems')
def api_hidden_systems():
    return jsonify(userdata.get_hidden_systems())


@app.route('/api/hidden-systems/toggle', methods=['POST'])
def api_toggle_hidden_system():
    data = request.get_json()
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
    data = request.get_json()
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'error': 'Path required'}), 400
    return jsonify(userdata.add_local_dir(path))


@app.route('/api/local-dirs', methods=['DELETE'])
def api_remove_local_dir():
    data = request.get_json()
    path = data.get('path', '').strip()
    return jsonify(userdata.remove_local_dir(path))


@app.route('/api/rom-dirs', methods=['GET'])
def api_get_rom_dirs():
    return jsonify(userdata.get_rom_dirs())


@app.route('/api/rom-dirs', methods=['POST'])
def api_add_rom_dir():
    data = request.get_json()
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'error': 'Path required'}), 400
    dirs = userdata.add_rom_dir(path)
    # Trigger rescan
    threading.Thread(target=_build_library, daemon=True).start()
    return jsonify(dirs)


@app.route('/api/rom-dirs', methods=['DELETE'])
def api_remove_rom_dir():
    data = request.get_json()
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

    return jsonify({
        'steam': {
            'connected': accounts.get('steam', {}).get('connected', False),
            'persona_name': accounts.get('steam', {}).get('persona_name', ''),
        },
        'gog_galaxy': {
            'available': galaxy_available,
            'enabled': accounts.get('gog_galaxy', {}).get('enabled', False),
            'connected_platforms': galaxy_platforms,
        },
        'epic': {
            'legendary_installed': EpicAccount.is_available(),
            'authenticated': EpicAccount.is_authenticated(),
        },
    })


@app.route('/api/accounts/steam/connect', methods=['POST'])
def api_connect_steam():
    """Connect a Steam account using API key + Steam ID or vanity URL."""
    data = request.get_json()
    api_key = data.get('api_key', '').strip()
    steam_id = data.get('steam_id', '').strip()

    if not api_key:
        return jsonify({'error': 'API key required'}), 400
    if not steam_id:
        return jsonify({'error': 'Steam ID or profile URL required'}), 400

    # Handle various Steam ID formats
    # Full profile URL: https://steamcommunity.com/id/vanityname or /profiles/76561...
    if 'steamcommunity.com' in steam_id:
        if '/id/' in steam_id:
            vanity = steam_id.split('/id/')[-1].strip('/')
            resolved = resolve_steam_vanity_url(api_key, vanity)
            if not resolved:
                return jsonify({'error': f'Could not resolve vanity URL: {vanity}'}), 400
            steam_id = resolved
        elif '/profiles/' in steam_id:
            steam_id = steam_id.split('/profiles/')[-1].strip('/')

    # If it looks like a vanity name (not all digits), resolve it
    if not steam_id.isdigit():
        resolved = resolve_steam_vanity_url(api_key, steam_id)
        if not resolved:
            return jsonify({'error': f'Could not resolve: {steam_id}'}), 400
        steam_id = resolved

    # Validate the connection
    steam = SteamAccount(api_key, steam_id)
    validation = steam.validate()

    if not validation['valid']:
        return jsonify({'error': validation['error']}), 400

    # Save account
    userdata.set_steam_account(api_key, steam_id, validation.get('persona_name', ''))

    # Trigger library rescan
    threading.Thread(target=_build_library, daemon=True).start()

    return jsonify({
        'status': 'connected',
        'persona_name': validation.get('persona_name', ''),
        'avatar': validation.get('avatar', ''),
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


@app.route('/api/accounts/epic/status')
def api_epic_status():
    """Check Epic/legendary availability and auth status."""
    return jsonify({
        'legendary_installed': EpicAccount.is_available(),
        'authenticated': EpicAccount.is_authenticated(),
    })


@app.route('/api/accounts/epic/auth', methods=['POST'])
def api_epic_auth():
    """Start Epic auth flow via legendary (opens browser)."""
    result = EpicAccount.start_auth()
    if result['status'] == 'ok':
        threading.Thread(target=_build_library, daemon=True).start()
    return jsonify(result)


@app.route('/api/settings/show-uninstalled', methods=['POST'])
def api_toggle_show_uninstalled():
    """Toggle showing uninstalled games from connected accounts."""
    settings = userdata.get_settings()
    new_val = not settings.get('show_uninstalled', True)
    userdata.update_settings({'show_uninstalled': new_val})
    threading.Thread(target=_build_library, daemon=True).start()
    return jsonify({'show_uninstalled': new_val})


# ── CatByte AI ──────────────────────────────────────────────────────────────

@app.route('/api/catbyte/status')
def api_catbyte_status():
    return jsonify(catbyte.check_status())


@app.route('/api/catbyte/chat', methods=['POST'])
def api_catbyte_chat():
    data = request.get_json()
    message = data.get('message', '')
    game_context = data.get('game_context', '')
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'Message required'}), 400

    # Auto-detect game context from active game
    if not game_context:
        _, current_game_id = _get_active()
        if current_game_id:
            with _library_lock:
                game = game_index.get(current_game_id, {})
            game_context = game.get('name', '')

    result = catbyte.chat(message, game_context=game_context, history=history)
    return jsonify(result)


@app.route('/api/catbyte/chat-vision', methods=['POST'])
def api_catbyte_chat_vision():
    data = request.get_json()
    message = data.get('message', '')
    image = data.get('image', '')
    game_context = data.get('game_context', '')
    history = data.get('history', [])

    if not message or not image:
        return jsonify({'error': 'Message and image required'}), 400

    if not game_context:
        _, current_game_id = _get_active()
        if current_game_id:
            with _library_lock:
                game = game_index.get(current_game_id, {})
            game_context = game.get('name', '')

    result = catbyte.chat_vision(message, image, game_context=game_context, history=history)
    return jsonify(result)


# ── Metadata ────────────────────────────────────────────────────────────────

@app.route('/api/metadata/<game_id>')
def api_metadata(game_id):
    """Get rich metadata for a game (description, genre, developer, etc.)."""
    with _library_lock:
        game = game_index.get(game_id)
    if not game:
        abort(404)

    meta = metadata_fetcher.get_metadata(
        game_id, game.get('name', ''),
        source=game.get('source', ''),
        system=game.get('system', ''),
    )
    return jsonify(meta or {})


@app.route('/api/metadata/stats')
def api_metadata_stats():
    """Get metadata cache statistics."""
    return jsonify(metadata_fetcher.db.get_stats())


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
    data = request.get_json()
    path = data.get('path', '').strip()
    if not path or not Path(path).exists():
        return jsonify({'error': 'Invalid path'}), 400

    settings = userdata.get_settings()
    bios_dirs = settings.get('bios_dirs', [])
    if path not in bios_dirs:
        bios_dirs.append(path)
        userdata.update_settings({'bios_dirs': bios_dirs})
        bios_manager.set_bios_dirs(bios_dirs)

    return jsonify(bios_manager.get_status())


@app.route('/api/bios/dirs', methods=['DELETE'])
def api_remove_bios_dir():
    data = request.get_json()
    path = data.get('path', '').strip()

    settings = userdata.get_settings()
    bios_dirs = settings.get('bios_dirs', [])
    if path in bios_dirs:
        bios_dirs.remove(path)
        userdata.update_settings({'bios_dirs': bios_dirs})
        bios_manager.set_bios_dirs(bios_dirs)

    return jsonify(bios_manager.get_status())


# ── Built-in Emulator ───────────────────────────────────────────────────────

# Systems that use the built-in emulator (EmulatorJS via webview)
BUILTIN_SYSTEMS = {
    'nes', 'snes', 'gb', 'gbc', 'gba',
    'megadrive', 'mastersystem', 'gamegear',
    'atari2600', 'ngp', 'psx',
    'neogeo', 'fbneo', 'cps1', 'cps2', 'cps3', 'mame',
    'nds', 'n64',
}


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

    return send_file(
        rom_path,
        mimetype='application/octet-stream',
        as_attachment=False,
        download_name=Path(rom_path).name,
    )


@app.route('/api/bios/<system>')
@app.route('/api/bios/<system>/<filename>')
def api_serve_bios(system, filename=None):
    """Serve BIOS files for the built-in emulator."""
    bios_path = bios_manager.get_bios_path(system, filename)
    if bios_path and Path(bios_path).exists():
        return send_file(bios_path, mimetype='application/octet-stream')
    abort(404)


@app.route('/api/emulator/info/<system>')
def api_emulator_info(system):
    """Check if a system uses the built-in emulator."""
    return jsonify({
        'system': system,
        'builtin': system in BUILTIN_SYSTEMS,
    })


# ── Assets ──────────────────────────────────────────────────────────────────

@app.route('/assets/audio/<filename>')
def assets_audio(filename):
    audio_dir = Path(__file__).parent / 'assets' / 'audio'
    audio_file = audio_dir / filename
    if audio_file.exists():
        return send_file(str(audio_file))
    abort(404)


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8745, debug=False, threaded=True)
