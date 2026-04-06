# YancoHub

Unified Windows game launcher — Flask backend (port 8745) + pywebview native window. Aggregates Steam, Epic, GOG, Xbox, EA, Ubisoft, Battle.net, local games, and retro ROMs into one dark cinematic interface with CatByte AI companion.

## What This Is

YancoHub is a unified game launcher — not a storefront, not a social network. It replaces the chaos of 8+ launchers with a single cinematic interface where every game you own is one click away. Built-in retro emulation (19 systems), multi-backend AI gaming companion, and a lightweight Python stack with no .NET or Electron dependencies.

## Commands

```bash
python launch.py                    # Run the app (Flask + pywebview)
python app.py                       # Flask backend only (dev mode)
pip install -r requirements.txt     # Install deps
python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt  # Fresh setup
python build.py                     # Build installer + portable zip (needs PyInstaller)
python build.py --portable          # Portable zip only
python build.py --installer         # NSIS installer only (needs makensis on PATH)
```

## Architecture

```
launch.py → starts Flask (app.py:8745) → waits for /health → opens pywebview window
                                        → optionally starts OpenClaw (CatByte AI:18789)

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
| `catbyte.py` | Multi-backend AI companion (Ollama, OpenClaw, LM Studio, OpenAI, custom) |
| `chathistory.py` | CatByte conversation history persistence |
| `constants.py` | Shared constants (VERSION, ports, LIBRETRO_SYSTEMS, VALID_ART_TYPES, BUILTIN_SYSTEMS, STEAM_CDN, LIBRETRO_THUMB) |
| `emusetup.py` | RetroArch + core auto-download and configuration |
| `launch.py` | App entry point — starts Flask subprocess + pywebview window |
| `romident.py` | ROM header parsing, fuzzy name matching, format priority |
| `window.py` | pywebview window API (folder/file browse dialogs, native menu bar) |
| `build.py` | PyInstaller + NSIS packaging for installer and portable zip |
| `installer.nsi` | NSIS installer script for Windows setup.exe |
| `static/js/app.js` | 3D hexagonal carousel, starfield, tabs, search, settings UI |
| `static/js/emulator.js` | EmulatorJS integration (19 retro systems in-browser via WASM) |

## Code Conventions

- Python: snake_case, type hints on public functions, `pathlib.Path` over `os.path`
- JS: camelCase functions, UPPER_SNAKE constants, vanilla JS (no frameworks)
- CSS: BEM-lite naming, CSS custom properties for all colors/sizes in `:root`
- Logger: `logger = logging.getLogger('yancohub.<module>')` in every Python module
- API responses: `{"status": "ok", ...}` or `{"error": "message"}` — always JSON
- Windows paths: backslashes in registry/filesystem, forward slashes in URLs
- Game IDs: composite strings like `steam_12345`, `epic_fortnite`, `rom_snes_abc123` — always `source_` prefixed

## Visual Identity — YancoVerse Theme

These values are **sacred**. Preserve them in all UI changes:

```
--bg:          #060b14     deep navy-black background
--accent:      #00e5c1     YancoVerse teal — glow, highlights, active states
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
7. **Verify visual changes** — describe what changed and confirm it matches YancoVerse aesthetic

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

## Legal Distribution Rules

- Ship only open-source BIOS (GBA: Cult-of-GBA MIT, PS1: OpenBIOS MIT)
- `.gitignore` excludes: `userdata.json`, `config/openclaw/USER.md`, `cache/`, `logs/`, proprietary BIOS
- Artwork fetched at runtime from public APIs, never bundled
- ROMs never referenced by path or included — only scanning logic ships
- No API keys, tokens, or personal paths in committed code
- GitHub noreply email: `YamanAddas@users.noreply.github.com`
