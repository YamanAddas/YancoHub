# YancoHub

Unified Windows game launcher — Flask backend (port 8745) + pywebview native window. Aggregates Steam, Epic, GOG, Xbox, EA, Ubisoft, Battle.net, local games, and retro ROMs into one dark cinematic interface with CatByte AI companion (OpenClaw, port 18789).

## What This Is

YancoHub is a **personal gaming cockpit** — not a storefront, not a social network. It replaces the chaos of 8+ launchers with a single cinematic interface where every game you own is one click away. Think GOG Galaxy's aggregation + LaunchBox/BigBox's visual polish + built-in retro emulation + an AI companion — in a lightweight, free, open-source Python app.

## Competitive Landscape (as of April 2026)

| App | What they do well | Where YancoHub wins |
|-----|-------------------|---------------------|
| **Playnite** v10.51 | Open source, 100+ plugins, fullscreen mode, IGDB metadata, huge community. WPF/.NET, ~200MB. Linux coming in P11 via Avalonia. | Lighter stack (no .NET). Built-in emulator (19 systems, no RetroArch needed). AI companion. Cinematic 3D carousel vs flat grid/list. |
| **LaunchBox/BigBox** v13.26 | Best visual polish (4K art, videos, manuals, EmuMovies). Huge theming. $30-75 premium. | Free. No .NET dependency. AI companion. Lighter weight. |
| **GOG Galaxy 2.0** | Official multi-store integration, friends/achievements across platforms. | Retro emulation built in. AI companion. Not tied to GOG ecosystem. More stores. |
| **Heroic Launcher** | Open source, Epic+GOG+Amazon, cross-platform (Electron). | More store support. Built-in emulator. AI companion. Not Electron. |

**Strategic position:** Beat Playnite on visual experience. Beat LaunchBox on accessibility (free, light, no runtime deps). The AI companion + built-in emulation are differentiators no competitor has.

## Commands

```bash
python launch.py                    # Run the app (Flask + pywebview)
python app.py                       # Flask backend only (dev mode)
pip install -r requirements.txt     # Install deps
python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt  # Fresh setup
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
| `catbyte.py` | OpenClaw proxy with offline fallback |
| `constants.py` | Shared constants (ports, LIBRETRO_SYSTEMS, VALID_ART_TYPES) |
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
