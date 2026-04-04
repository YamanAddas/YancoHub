# YancoHub — Architecture Reference

## Data Flow

```
User opens app
  → launch.py starts Flask subprocess on port 8745
  → launch.py waits for /health to return 200
  → launch.py opens pywebview window pointing at http://127.0.0.1:8745
  → Flask fires _initial_scan() in daemon thread
    → scanner.scan_all() reads registries, manifests, DBs, directories
    → accounts module fetches Steam API / GOG Galaxy DB / Epic legendary
    → _build_library() merges local + account games by ID then by name
    → enrichment thread fetches metadata (Steam Store + Wikipedia) and artwork (CDN cascade)
  → Frontend polls /api/games → renders carousel
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

### Required Fix: Atomic Swap

**Never mutate `game_library` or `game_index` in place.** Build into local variables, then assign:

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

### Known Bug: Epic ID Mismatch

**scanner.py** uses `epic_{make_game_id('epic', app_name)}` (MD5 hash) but **accounts.py** uses `epic_{app_name}` (raw string). These will never match during merge.

**Fix:** Use `epic_{app_name}` consistently in both files.

### Known Bug: GOG ID Mismatch

**scanner.py** uses `gog_{registry_GAMEID}` but **accounts.py** uses `gog_{releaseKey_suffix}`. These may differ.

**Fix:** Normalize both to the same format. The registry GAMEID is the most reliable since it comes from GOG's own installer.

## Library Merge Logic

`_build_library()` merges two sources:

1. **Local scan** (installed games) — always have `installed: True`
2. **Account games** (owned but maybe not installed) — start with `installed: False`

Merge priority:
1. Match by ID → local version wins, merge artwork/playtime from account
2. Match by name (case-insensitive) → skip the account duplicate
3. No match → add as uninstalled (if `show_uninstalled` setting is on)

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

### Known Bug: GOG Galaxy DB Wrong Table

**scanner.py:316** queries `InstalledBaseProducts` which doesn't exist. The correct tables are `LibraryReleases`, `GamePieces`, `GamePieceTypes` (as used in accounts.py).

### Known Bug: GOG Galaxy DB Not Read-Only

**scanner.py:313** opens the DB in read-write mode. Must use `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`.

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

### Known Bug: Command Injection

**app.py:276** uses `shell=True`. This is a security vulnerability — shell metacharacters in game paths/names could execute arbitrary commands.

**Fix:** Use `shell=False` with `shlex.split()` or argument lists. For emulator commands built as strings with quotes, parse them into lists properly.

### Known Bug: Emulator Session Never Ends

`exitEmulator()` in emulator.js doesn't call the backend to end the session. The `active_game_id` stays set forever.

**Fix:** Add `fetch('/api/session/end/' + emuGameId, {method: 'POST'})` to `exitEmulator()` and create the endpoint.

### Known Bug: URL Monitor Unreliable

`_start_url_monitor()` matches game names against process names by splitting on spaces and checking if any word > 3 chars appears in any running process name. This is fundamentally broken for many games.

**Better approach:** Timer-based with user prompt, or track the store launcher process itself.

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

```
D:\yancohub\                    Project root (development)
  app.py, scanner.py, ...       Python modules
  static\                       Frontend assets
  templates\index.html          SPA template
  cache\artwork\                Downloaded art (gitignored)
  cache\metadata.db             SQLite metadata cache (gitignored)
  userdata.json                 User settings (gitignored)
  logs\yancohub.log             App log (gitignored)
  bios\                         Open-source BIOS files
  bios\user\                    User-provided BIOS (gitignored)
  config\openclaw\              CatByte AI config (gitignored)
```

## API Endpoint Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Backend readiness check |
| GET | `/api/games` | Full game library (filtered by source/system) |
| GET | `/api/search?q=` | Search games by name |
| POST | `/api/launch/<id>` | Launch a game |
| GET | `/api/active-game` | Currently running game |
| POST | `/api/rescan` | Trigger full library rescan |
| GET | `/api/artwork/<id>/<type>` | Get game artwork (cover/header/hero/logo) |
| GET | `/api/metadata/<id>` | Get game metadata |
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
| GET | `/api/accounts/epic/status` | Epic auth status |
| POST | `/api/accounts/epic/auth` | Start Epic auth flow |
| GET | `/api/stores` | Detected store installations |
| GET | `/api/playtime` | All playtime data |
| GET | `/api/last-played` | Last played game ID |
| POST | `/api/catbyte/chat` | Chat with CatByte AI |
| POST | `/api/catbyte/chat-vision` | Chat with screenshot |
| GET | `/api/catbyte/status` | CatByte online/offline |
| POST | `/api/settings/show-uninstalled` | Toggle uninstalled games visibility |
| GET | `/api/hidden-systems` | Hidden retro systems |
| POST | `/api/hidden-systems/toggle` | Toggle system visibility |
