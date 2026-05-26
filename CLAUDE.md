# YancoHub

Unified Windows game launcher — Flask backend (port 8745) + pywebview native window. Aggregates Steam, Epic, GOG, Xbox, EA, Ubisoft, Battle.net, local games, and retro ROMs into one dark cinematic interface with CatByte AI companion.

## What This Is

YancoHub is a unified game launcher — not a storefront, not a social network. It replaces the chaos of 8+ launchers with a single cinematic interface where every game you own is one click away. Built-in retro emulation (19 systems), multi-backend AI gaming companion, and a lightweight Python stack with no .NET or Electron dependencies.

## Commands

```bash
python launch.py                    # Run the app (Flask + pywebview)
python app.py                       # Flask backend only (dev mode)
pip install -r requirements.txt     # Install runtime deps
pip install -r requirements-dev.txt # Install runtime + test deps (pytest)
python -m venv venv && venv\Scripts\activate && pip install -r requirements-dev.txt  # Fresh setup
python build.py                     # Build installer + portable zip (needs PyInstaller)
python build.py --portable          # Portable zip only
python build.py --installer         # Installer only (Inno Setup preferred, NSIS fallback)
python -m pytest tests/ -v          # Run all tests (328 tests)
python -m pytest tests/test_app.py  # Run Flask route tests only
python -m pytest tests/ -k fuzzy    # Run tests matching keyword
```

## Architecture

```
launch.py → starts Flask (app.py:8745) → waits for /health → opens pywebview window

Frontend: single-page app served by Flask (templates/index.html + static/)
Backend:  REST API (app.py) orchestrating scanner, accounts, metadata, artwork, BIOS, catbyte
Storage:  userdata.json (settings/favorites/playtime) + cache/metadata.db (SQLite) + cache/artwork/
```

**Modules:**
| File | Responsibility |
|------|----------------|
| `app.py` | Flask routes, library builder, game launcher, process monitor |
| `scanner.py` | Detect installed games from 8 stores + local dirs + ROM dirs |
| `accounts.py` | Steam Web API, GOG Galaxy DB, Epic catalog cache (+ legendary fallback) |
| `metadata.py` | Steam Store API + Wikipedia REST API → SQLite cache |
| `artwork.py` | Steam CDN → LibRetro thumbnails → SteamGridDB → fallback gradient |
| `biosmanager.py` | Auto-detect BIOS files by filename/MD5, per-system readiness |
| `userdata.py` | JSON persistence for settings, playtime, collections |
| `settings_schema.py` | Single source of truth for key/value settings (type, default, validation, UI metadata) — drives DEFAULT_DATA and the unified `/api/settings` endpoints |
| `catbyte.py` | Multi-backend AI companion (Ollama, OpenClaw, LM Studio, OpenAI, custom) |
| `chathistory.py` | CatByte conversation history persistence |
| `constants.py` | Shared constants (VERSION, ports, LIBRETRO_SYSTEMS, VALID_ART_TYPES, BUILTIN_SYSTEMS, STEAM_CDN, LIBRETRO_THUMB) |
| `emusetup.py` | RetroArch + core auto-download and configuration |
| `launch.py` | App entry point — starts Flask (subprocess in dev, daemon thread when frozen) + pywebview window, health watchdog |
| `romident.py` | ROM header parsing, fuzzy name matching, format priority |
| `window.py` | pywebview window API (folder/file browse dialogs, native menu bar) |
| `paths.py` | Centralized data paths (%APPDATA%, %LOCALAPPDATA%), portable mode, migration |
| `singleinstance.py` | Windows named mutex for single-instance enforcement |
| `dpi.py` | Per-Monitor V2 DPI awareness via ctypes fallback chain |
| `updatecheck.py` | GitHub Releases API update checker (background thread) |
| `startup.py` | Windows startup registry (HKCU\...\Run) toggle |
| `gamepad.py` | Direct HID controller support (DualSense/DS4) bridged to the frontend |
| `overlay.py` | CatByte in-game overlay — F10 global hotkey, always-on-top pywebview window |
| `build.py` | PyInstaller + Inno Setup (NSIS fallback) packaging, code signing hooks, portable zip |
| `installer.iss` | Inno Setup installer script (primary) with protocol handler registration |
| `installer.nsi` | NSIS installer script (fallback) with protocol handler registration |
| `static/js/app.js` | 3D hexagonal carousel, starfield, tabs, search, settings UI |
| `static/js/overlay.js` | Standalone CatByte chat JS for in-game overlay window |
| `static/css/overlay.css` | Overlay-specific styles (glassmorphism, slide-in animation) |
| `static/js/emulator.js` | EmulatorJS integration (19 retro systems in-browser via WASM) |

**Tests:**
| File | Covers |
|------|--------|
| `tests/conftest.py` | Shared fixtures: temp dirs, UserData, ChatHistory, MetadataDB, synthetic ROM builders |
| `tests/test_constants.py` | Version format, ports, LIBRETRO_SYSTEMS integrity, BUILTIN_SYSTEMS subset |
| `tests/test_romident.py` | SNES/GB/GBC/GBA/Genesis/N64 header parsing, byte-swap, fuzzy matching |
| `tests/test_userdata.py` | Sessions, collections, favorites, hidden systems, dirs, accounts, persistence |
| `tests/test_biosmanager.py` | BIOS scanning, subfolders, case-insensitive matching, aliases, status |
| `tests/test_chathistory.py` | Session CRUD, pinning, messages, LLM formatting, pruning |
| `tests/test_metadata.py` | SQLite cache CRUD, Steam/Wikipedia fetching (mocked HTTP), enrichment |
| `tests/test_app.py` | Flask routes: health, games, search, collections, favorites, CSRF, artwork |
| `tests/test_paths.py` | Portable detection, APPDATA/LOCALAPPDATA paths, migration |
| `tests/test_singleinstance.py` | Mutex acquisition/release, already-running detection |
| `tests/test_updatecheck.py` | Version parsing, newer/same/older comparison, mocked HTTP |
| `tests/test_startup.py` | Mock winreg read/write/delete for startup registry |
| `tests/test_gamepad.py` | HID controller parsing, button mapping, bridge state |
| `tests/test_security.py` | Path validation, origin checks, prompt-injection sanitization |
| `tests/test_settings_schema.py` | Setting defaults, type/path/int-map validation, public schema |

## Code Conventions

- Python: snake_case, type hints on public functions, `pathlib.Path` over `os.path`
- JS: camelCase functions, UPPER_SNAKE constants, vanilla JS (no frameworks)
- CSS: BEM-lite naming, CSS custom properties for all colors/sizes in `:root`
- Logger: `logger = logging.getLogger('yancohub.<module>')` in every Python module
- API responses: `{"status": "ok", ...}` or `{"error": "message"}` — always JSON
- Windows paths: backslashes in registry/filesystem, forward slashes in URLs
- Game IDs: composite strings like `steam_12345`, `epic_fortnite`, `rom_snes_abc123` — always `source_` prefixed

## Visual Identity

These values are **sacred**. Preserve them in all UI changes:

```
--bg:          #060b14     deep navy-black background
--accent:      #00e5c1     teal — glow, highlights, active states
--text:        #8a9bb0     muted blue-gray body text
--text-bright: #c8d6e5     headings, important text
--card-width:  180px
--card-height: 320px
--hex-point:   9%          hexagonal crystal card clip-path
```

- Font: Inter (Google Fonts) → system sans-serif fallback
- Effects: starfield canvas, glassmorphism (backdrop-filter: blur), glow/breathing animations, hex clip-path cards
- 3D carousel: `perspective: 900px`, `rotateY`, `translateZ`, `scale` with 4 visible cards per side
- Per-system accent colors in `SYS_COLORS` (app.js)

## Quality Bar

Every change must meet ALL of these:

1. **No regressions** — what worked before still works after
2. **No silent failures** — errors logged with context, never bare `except: pass`
3. **No broken state** — if an operation fails midway, app remains usable
4. **Thread safety** — mutations to `game_library`, `game_index`, `active_process`, `active_game_id` must use atomic swap or lock
5. **No `shell=True`** — all subprocess calls use argument lists
6. **Visual consistency** — all UI uses CSS variables from `:root`, never hardcoded colors
7. **Verify visual changes** — describe what changed and confirm it matches the YancoHub aesthetic
8. **Tests pass** — run `python -m pytest tests/ -v` before considering a change complete; all 328 tests must pass
9. **New logic gets tests** — any new module, function, or route should have corresponding tests in `tests/`; use existing fixtures from `conftest.py` (temp dirs, synthetic ROMs, mocked HTTP)
10. **Data paths use `paths.py`** — never hardcode `userdata.json`, `cache/`, or `logs/` paths; always use `get_data_dir()`, `get_cache_dir()`, `get_log_dir()`
11. **New settings go in `settings_schema.py`** — add a key/value setting to the `SETTINGS` registry (type, default, tab, label, hint, optional `validate`/`side_effect`/`backend`). This auto-populates `DEFAULT_DATA['settings']` and the `/api/settings` endpoints — never add a setting straight into `userdata.py` or a one-off endpoint

## Gotchas

- **pywebview blocks the main thread** — Flask runs in a subprocess, not a background thread
- **Steam API rate limits** — always check `MetadataDB` cache before fetching; 0.2s delay between batch requests
- **GOG Galaxy DB is read-only** — never write to `galaxy-2.0.db`; always open with `?mode=ro` URI
- **Epic catalog cache** — `catcache.bin` at `ProgramData/Epic/EpicGamesLauncher/Data/Catalog/` is auto-populated when user logs into Epic Launcher; legendary CLI is a fallback only
- **EmulatorJS loads from CDN** (`cdn.emulatorjs.org`) — needs internet for first retro game launch; cores cached by browser
- **Windows registry keys vary by bitness** — use `KEY_READ | KEY_WOW64_32KEY` or `KEY_WOW64_64KEY`
- **`userdata.json` is single source of truth** for user prefs — never split config across files
- **Process monitoring** — `pid.is_running()` can return True briefly after exit; poll with status check
- **Direct launch** — `direct_exe` paths are Windows paths; never `shlex.split()` them (spaces break). Use `[exe_path]` as a list. `direct_args` can be split with `shlex.split(args, posix=False)`
- **GOG `goggame-*.info`** — JSON files in install dir with `playTasks` array; `isPrimary` + `type: "FileTask"` gives the main exe. All GOG games are DRM-free
- **Frozen vs dev Flask** — `launch.py` runs Flask as a subprocess in dev mode, but in-process on a daemon thread when frozen (PyInstaller `sys.executable` is the exe, not python). The watchdog restart kills the old subprocess first (dev) and cannot restart a hung in-process server (frozen) — it surfaces a fatal-error overlay instead
- **Named mutex auto-release** — Windows automatically releases the mutex when the process exits (even on crash), so no stale lock files
- **Portable mode detection** — `paths.is_portable()` checks for `portable.txt` next to the exe; portable zip includes this file, installer does not
- **%APPDATA% migration** — `migrate_legacy_data()` runs once at startup; copies files then renames originals to `.migrated` suffix to prevent double-migration
- **CatByte overlay** — second pywebview window (frameless, on_top); F10 global hotkey via `RegisterHotKey` works even when game has focus; only appears over borderless/windowed games (~95% of modern titles); hidden when not in use to avoid GSync/FreeSync issues

## Testing

Tests use `pytest` with temp files and mocks — no network or filesystem side effects.

```bash
python -m pytest tests/ -v          # Full suite (328 tests, ~4s)
python -m pytest tests/ -k "rom"    # Run only ROM-related tests
python -m pytest tests/test_app.py  # Flask routes only
```

**Writing new tests:**
- Use fixtures from `conftest.py`: `userdata_instance`, `chat_history_instance`, `metadata_db`, `bios_manager`, `rom_dir`
- Synthetic ROM helpers: `make_snes_rom()`, `make_gb_rom()`, `make_gba_rom()`, `make_genesis_rom()`, `make_n64_rom()`
- For Flask routes: use the `client` fixture in `test_app.py` — it mocks all backend services and restores originals after each test
- Mock HTTP calls with `unittest.mock.patch` — never hit real APIs in tests
- Use `tmp_path` (pytest built-in) for any file I/O — never write to real project paths

## What Not To Do

- Introduce npm, webpack, or any JS build system — this is vanilla JS served by Flask
- Add frameworks beyond Flask — no Django, FastAPI, SQLAlchemy ORM
- Bundle copyrighted content (BIOS, ROMs, proprietary artwork, sounds)
- Create separate HTML pages — single-page app, use overlays/panels in `index.html`
- Change the hex card shape or carousel 3D math without explicit request
- Use `os.path` when `pathlib.Path` works
- Add dependencies without updating `requirements.txt`
- Use `shell=True` in any subprocess call
- Swallow exceptions with bare `except: pass`
- Hardcode colors instead of using CSS variables
- Skip running tests before marking a change complete
- Write tests that hit real APIs, real filesystems, or depend on installed games

## Legal Distribution Rules

- Ship only open-source BIOS (GBA: Cult-of-GBA MIT, PS1: OpenBIOS MIT)
- `.gitignore` excludes: `userdata.json`, `cache/`, `logs/`, proprietary BIOS
- Artwork fetched at runtime from public APIs, never bundled
- ROMs never referenced by path or included — only scanning logic ships
- No API keys, tokens, or personal paths in committed code
- GitHub noreply email: `YamanAddas@users.noreply.github.com`
