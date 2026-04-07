# YancoHub — Architecture Reference

## Data Flow

```
User opens app
  → launch.py: enable DPI awareness (ctypes)
  → launch.py: acquire single-instance mutex (kernel32.CreateMutexW)
  → launch.py: migrate legacy data from app dir to %APPDATA% (one-time)
  → launch.py: start Flask subprocess on port 8745
  → launch.py: wait for /health to return 200
  → launch.py: start health watchdog daemon thread (pings /health every 5s)
  → launch.py: open pywebview window (or hidden if --minimized)
  → Flask fires _initial_scan() in daemon thread
    → scanner.scan_all() reads registries, manifests, DBs, directories
    → accounts module fetches Steam API / GOG Galaxy DB / Epic catalog cache
    → _build_library() merges local + account games by ID then by name
    → enrichment thread fetches metadata (Steam Store + Wikipedia) and artwork (CDN cascade)
    → start_update_check() fires GitHub API check in background thread
  → Frontend polls /api/games → renders carousel
  → Frontend checks /api/onboarding/status → shows onboarding if first run
  → Frontend checks /api/update-available (3s delay) → shows update banner if newer
  → System tray icon started (pystray) if minimize_to_tray enabled
```

### Health Watchdog

```
launch.py health_watchdog thread:
  loop every 5s:
    GET /health → 200? → reset failure count
    failure? → increment count
    3 consecutive failures → notify frontend (showConnectionError)
                           → restart Flask subprocess
                           → max 5 restarts → showFatalError, stop
```

### Protocol Handler

```
yancohub://launch/{game_id}  → launches a specific game
yancohub://settings           → opens settings panel

Second instance with protocol URL:
  → mutex already exists → POST url to /api/protocol-action → exit
First instance with protocol URL:
  → store URL → pass to Flask after startup
```

## Thread Safety Pattern

The app has shared mutable globals that are read from request threads and written from scan/monitor threads:

```python
# GLOBALS (app.py)
game_library = []        # written by _build_library(), read by /api/games
game_index = {}           # written by _build_library(), read by /api/launch, /api/artwork, etc.
active_process = None     # written by monitor threads, read by /api/active-game
active_game_id = None     # written by monitor threads, read by /api/catbyte/chat
```

### Pattern: Atomic Swap

`game_library` and `game_index` are never mutated in place. They are built into local variables, then assigned under lock:

```python
import threading

_library_lock = threading.Lock()

def _build_library():
    global game_library, game_index

    # Build into locals
    new_library = []
    # ... all scan + merge logic ...
    new_index = {g['id']: g for g in new_library}

    # Atomic swap
    with _library_lock:
        game_library = new_library
        game_index = new_index
```

For `active_process` / `active_game_id`, use a separate lock:

```python
_active_lock = threading.Lock()

def set_active(proc, game_id):
    global active_process, active_game_id
    with _active_lock:
        active_process = proc
        active_game_id = game_id

def clear_active(game_id):
    global active_process, active_game_id
    with _active_lock:
        if active_game_id == game_id:
            active_process = None
            active_game_id = None
```

## Game ID Strategy

Game IDs are the primary key for merging, deduplication, favorites, playtime, and collections. They must be **stable** (same game always gets the same ID) and **unique** (no collisions across stores).

| Source | ID Format | Example |
|--------|-----------|---------|
| Steam | `steam_{appid}` | `steam_1174180` |
| Epic | `epic_{app_name}` | `epic_Fortnite` |
| GOG (registry) | `gog_{game_id}` | `gog_1495134320` |
| GOG (Galaxy DB) | `gog_{game_id_raw}` | `gog_1495134320` |
| Xbox | `xbox_{hash}` | `xbox_a1b2c3d4e5f6` |
| EA | `ea_{hash}` | `ea_f7e8d9c0b1a2` |
| Ubisoft | `ubisoft_{registry_key}` | `ubisoft_3234` |
| Battle.net | `bnet_{product_code}` | `bnet_Pro` |
| Local | `local_{hash}` | `local_c4d5e6f7a8b9` |
| Retro ROM | `rom_{hash}` | `rom_a1b2c3d4e5f6` |

### ~~Known Bug: Epic ID Mismatch~~ FIXED

Both scanner and accounts now use `epic_{app_name}` consistently.

### ~~Known Bug: GOG ID Mismatch~~ FIXED

Both scanner and accounts now use consistent GOG ID format.

## Library Merge Logic

`_build_library()` merges two sources:

1. **Local scan** (installed games) — always have `installed: True`
2. **Account games** (owned but maybe not installed) — start with `installed: False`

Merge priority:
1. Match by ID → local version wins, merge artwork/playtime from account
2. Match by name (case-insensitive) → skip the account duplicate
3. No match → add as uninstalled (if `show_uninstalled` setting is on)

## Direct Launch

When the `direct_launch` setting is on (default: true), games launch via their executable directly instead of through store protocol URLs (`steam://`, `com.epicgames.launcher://`, etc.).

**Exe detection at scan time** — each scanner populates `direct_exe` and `direct_args` fields:

| Store | Detection method | Reliability |
|-------|-----------------|-------------|
| Steam | Heuristic exe search in install dir (name match → largest file) | Good — most games found, Steamworks DRM may still block |
| Epic | `LaunchExecutable` field from `.item` manifest | High — direct from Epic's own metadata |
| GOG (registry) | `EXE` registry value, fallback to `goggame-*.info` parsing | High — all GOG games are DRM-free |
| GOG (Galaxy DB) | `InstalledBaseProducts` table → `goggame-*.info` | High for installed games |

**Launch flow** (`api_launch`):
1. If `direct_launch` ON and `direct_exe` exists on disk → `subprocess.Popen([exe, *args])` with process monitoring
2. Else if `launch_cmd` is a protocol URL → `os.startfile()` with PID-snapshot monitoring
3. Else → `subprocess.Popen(shlex.split(launch_cmd))` (local games, ROMs)

## Scanner Architecture

Each `_scan_*` method appends to `self.games`. They run sequentially in `scan_all()`:

```
_scan_steam()       — Registry → library folders → ACF manifests
_scan_epic()        — ProgramData manifests (.item JSON)
_scan_gog()         — Registry first, Galaxy DB fallback
_scan_xbox()        — XboxGames dir + PowerShell Get-AppxPackage
_scan_ea()          — ProgramData XML + Registry
_scan_ubisoft()     — Registry Installs keys
_scan_battlenet()   — AppData config JSON
_scan_local_dir()   — Subdirectory scan for .exe files
_scan_roms()        — System subdirectories → extension matching → dedup by format priority
```

### ~~Known Bug: GOG Galaxy DB Wrong Table~~ FIXED

Uses correct `LibraryReleases` table.

### ~~Known Bug: GOG Galaxy DB Not Read-Only~~ FIXED

Opens with `?mode=ro` URI.

## Launch Flow

```
/api/launch/<game_id>  POST
  → look up game in game_index
  → game.launch_cmd determines path:

  URL protocol (steam://, com.epicgames.launcher://, etc.)
    → os.startfile(launch_cmd)
    → _start_url_monitor() in daemon thread
    → polls psutil every 10s looking for matching process name

  Direct executable
    → subprocess.Popen(args, shell=False)    # MUST be shell=False
    → _start_process_monitor() waits on proc.wait()
    → session_end() on exit

  Built-in emulator (retro, system in BUILTIN_SYSTEMS)
    → handled client-side by emulator.js
    → boot sequence animation → EmulatorJS loads from CDN
    → session end MUST be signaled by exitEmulator() calling backend
```

### ~~Known Bug: Command Injection~~ FIXED

Uses `shell=False` with `shlex.split()`.

### ~~Known Bug: Emulator Session Never Ends~~ FIXED

`exitEmulator()` calls `/api/session/end/<game_id>`.

### ~~Known Bug: URL Monitor Unreliable~~ FIXED

Uses process-snapshot diffing: snapshots PIDs before launch, identifies new large processes (>50MB), monitors those specific PIDs until exit. Falls back to 30-min timeout if no clear game process found. Manual session end always available via `/api/session/end/<game_id>`.

## Artwork Cascade

```
1. game.artwork[art_type] → local file (Steam cache)
2. artwork_scraper.get_artwork_path() → check local cache
3. Steam CDN → https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/...
4. LibRetro thumbnails → for retro games
5. SteamGridDB API → community-provided art
6. Fallback → CSS gradient with system colors + emoji icon
```

## Metadata Cascade

```
1. MetadataDB SQLite cache (check first, always)
2. Steam Store API → store.steampowered.com/api/appdetails
3. Wikipedia REST API → en.wikipedia.org/api/rest_v1/page/summary
```

## EmulatorJS Integration

- 19 systems in `BUILTIN_SYSTEMS` (emulator.js), 7 in `EXTERNAL_SYSTEMS` (need RetroArch/standalone)
- CDN: `https://cdn.emulatorjs.org/stable/data/`
- System→core mapping defines EmulatorJS core names (e.g., `megadrive` → `segaMD`)
- ROMs served via `/api/rom/<game_id>` — Flask streams from user's local file
- BIOS served via `/api/bios/<system>/<filename>`
- EJS globals set before loading `loader.js`: `EJS_player`, `EJS_core`, `EJS_gameUrl`, etc.

## File Paths (Windows)

All paths managed by `paths.py`. Portable mode (detected via `portable.txt` marker) keeps everything in the app directory.

### Normal Mode (installed)
```
%APPDATA%\YancoHub\
  userdata.json                 User settings, favorites, playtime
  catbyte_history.json          CatByte conversation history

%LOCALAPPDATA%\YancoHub\
  cache\artwork\                Downloaded artwork
  cache\metadata.db             SQLite metadata cache
  logs\yancohub.log             App log (5MB rotating, 3 backups)
```

### Portable Mode (`portable.txt` next to exe)
```
YancoHub\
  portable.txt                  Marker file (presence enables portable mode)
  userdata.json                 User settings
  catbyte_history.json          CatByte history
  cache\artwork\                Downloaded artwork
  cache\metadata.db             Metadata cache
  logs\yancohub.log             App log
  bios\                         Open-source BIOS files
  bios\user\                    User-provided BIOS
```

### Registry Keys (installer only)
```
HKCU\Software\YancoHub                                        InstallDir
HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\...  Add/Remove Programs
HKCU\Software\Classes\yancohub                                Protocol handler (yancohub://)
HKCU\Software\Microsoft\Windows\CurrentVersion\Run             Startup toggle (optional)
```

## Test Architecture

Tests live in `tests/` and run via `pytest` (config in `pyproject.toml`). No network access, no real filesystem writes.

```
tests/
  conftest.py          — Shared fixtures + synthetic ROM builders
  test_constants.py    — Validates constant definitions and cross-references
  test_romident.py     — ROM header parsing for 5 systems + fuzzy matching
  test_userdata.py     — Full CRUD coverage for UserData (sessions, collections, etc.)
  test_biosmanager.py  — BIOS scanning with temp directories
  test_chathistory.py  — CatByte session management + pruning
  test_metadata.py     — SQLite cache + mocked Steam/Wikipedia fetchers
  test_app.py          — Flask test client with mocked backend singletons
```

**Key patterns:**
- `conftest.py` provides fixtures: `userdata_instance`, `chat_history_instance`, `metadata_db`, `bios_manager` — all backed by `tmp_path`
- Synthetic ROM files: `make_snes_rom(path, title)` etc. build minimal valid binaries with embedded titles at correct header offsets
- `test_app.py` replaces module-level singletons (`userdata`, `scanner`, `metadata_fetcher`, etc.) with `MagicMock` objects, then restores originals after each test
- HTTP calls in metadata tests are mocked via `unittest.mock.patch` on the `requests.Session`
- CSRF protection is tested with valid/invalid Origin and Referer headers

## API Endpoint Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Backend readiness check |
| GET | `/api/games` | Full game library (filtered by source/system) |
| GET | `/api/search?q=` | Search games by name |
| POST | `/api/launch/<id>` | Launch a game |
| POST | `/api/rescan` | Trigger full library rescan |
| GET | `/api/artwork/<id>/<type>` | Get game artwork (cover/header/hero/logo) |
| POST | `/api/favorites/toggle` | Toggle game favorite |
| GET/POST/DELETE | `/api/collections` | Manage collections |
| GET/POST/DELETE | `/api/rom-dirs` | Manage ROM directories |
| GET/POST/DELETE | `/api/local-dirs` | Manage local game directories |
| GET/POST/DELETE | `/api/bios/dirs` | Manage BIOS directories |
| GET | `/api/bios/status` | Per-system BIOS readiness |
| GET | `/api/bios/<system>` | Serve BIOS file to emulator |
| GET | `/api/rom/<game_id>` | Serve ROM file to emulator |
| POST | `/api/accounts/steam/connect` | Connect Steam account |
| POST | `/api/accounts/steam/disconnect` | Disconnect Steam |
| POST | `/api/accounts/gog-galaxy/toggle` | Toggle GOG Galaxy |
| POST | `/api/accounts/epic/auth` | Start Epic auth flow |
| GET | `/api/stores` | Detected store installations |
| GET | `/api/playtime` | All playtime data |
| POST | `/api/catbyte/chat` | Chat with CatByte AI |
| POST | `/api/catbyte/chat-vision` | Chat with screenshot |
| GET | `/api/catbyte/status` | CatByte online/offline |
| POST | `/api/settings/show-uninstalled` | Toggle uninstalled games visibility |
| GET/POST | `/api/settings/direct-launch` | Toggle direct game launching (bypass store clients) |
| GET/POST | `/api/settings/retroarch-path` | Get/set RetroArch path |
| GET/POST | `/api/settings/launchbox-path` | Get/set LaunchBox path |
| GET | `/api/hidden-systems` | Hidden retro systems |
| POST | `/api/hidden-systems/toggle` | Toggle system visibility |
| GET | `/api/update-available` | Check for newer GitHub release |
| GET/POST | `/api/settings/launch-on-startup` | Windows startup toggle |
| GET/POST | `/api/settings/minimize-to-tray` | Minimize-to-tray toggle |
| GET | `/api/onboarding/status` | First-run onboarding status |
| POST | `/api/onboarding/complete` | Mark onboarding complete |
| POST | `/api/protocol-action` | Handle yancohub:// protocol URLs |
