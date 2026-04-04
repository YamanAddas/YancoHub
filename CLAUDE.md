# YancoHub — Unified Game Launcher for Windows

## What This Is

YancoHub is a unified PC game launcher for Windows that aggregates games from all major stores (Steam, Epic, GOG, Xbox Game Pass, EA Play, Ubisoft Connect, Battle.net), local/portable games, and retro ROMs into one dark, cinematic interface — the same YancoVerse aesthetic as YancoDeck (PS5-like fluidity, glassmorphism, teal accent). Includes CatByte AI gaming companion via OpenClaw.

## Project Location

```
D:\yancohub\
  launch.py                             — Main entry point
  app.py                                — Flask backend (port 8745) + all API endpoints
  window.py                             — pywebview window (renders Flask UI)
  scanner.py                            — Game library scanner (Steam, Epic, GOG, Xbox, etc.)
  userdata.py                           — Persistent user data (play time, collections, favorites)
  catbyte.py                            — CatByte AI integration (OpenClaw proxy)
  userdata.json                         — Persisted data file (auto-created)
  requirements.txt                      — Python dependencies
  logs/                                 — Runtime logs
  cache/artwork/                        — Cached game artwork
  assets/audio/                         — Sound files
  config/openclaw/                      — CatByte persona files (SOUL.md, USER.md, AGENTS.md)
  static/css/style.css                  — Dark cinematic theme
  static/js/app.js                      — Frontend JS
  static/img/logo.png                   — YancoHub logo
  static/img/systems/                   — Console/platform artwork
  templates/index.html                  — Main UI template
  YancoDeck-main/                       — Reference: original YancoDeck codebase
```

## Architecture

```
User double-clicks launch.py (or YancoHub.bat)
  → launch.py starts Flask backend (app.py) on port 8745
  → launch.py waits for Flask health check
  → launch.py opens pywebview window loading http://127.0.0.1:8745
  → pywebview BLOCKS until window closed
  → On close: cleanup, exit

Game launching:
  → Steam: steam://run/<appid> (via shell)
  → Epic: com.epicgames.launcher://apps/<namespace>?action=launch
  → GOG: goggalaxy://openGameView/<game_id> or direct .exe
  → Xbox/Game Pass: shell:AppsFolder\<package>!App or direct .exe
  → EA Play: link2ea://launchgame/<content_id>
  → Ubisoft: uplay://launch/<id>/0
  → Battle.net: battlenet://<code>
  → Local games: direct subprocess
  → Retro ROMs: RetroArch.exe -L <core.dll> <rom>
```

## Game Sources (Windows)

### Steam
- Registry: `HKCU\Software\Valve\Steam\SteamPath`
- Library folders: `<steam>/steamapps/libraryfolders.vdf`
- Parse `appmanifest_*.acf` for installed games
- Artwork: `<steam>/appcache/librarycache/<appid>/`
- Launch: `steam://run/<appid>`

### Epic Games Store
- Manifests: `C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item`
- Each .item is JSON with DisplayName, InstallLocation, AppName, etc.
- Launch: `com.epicgames.launcher://apps/<namespace>?action=launch`

### GOG Galaxy
- Database: `C:\ProgramData\GOG.com\Galaxy\storage\galaxy-2.0.db` (SQLite)
- Registry: `HKLM\SOFTWARE\WOW6432Node\GOG.com\Games\*`
- Launch: `goggalaxy://openGameView/<id>` or direct exe

### Xbox / Game Pass
- Registry: `HKLM\SOFTWARE\Microsoft\GamingServices`
- PowerShell: `Get-AppxPackage -Name *Microsoft.Gaming*`
- XboxGamePassPC: scan `C:\Program Files\WindowsApps\` or `C:\XboxGames\`
- Launch: `shell:AppsFolder\<PackageFamilyName>!App`

### EA Play (EA Desktop / Origin)
- XML: `C:\ProgramData\EA Desktop\InstallData\*`
- Registry: `HKLM\SOFTWARE\WOW6432Node\Electronic Arts\EA Desktop\InstallSuccessful`
- Launch: `link2ea://launchgame/<content_id>` or origin://

### Ubisoft Connect
- Registry: `HKLM\SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs\*`
- Config: `C:\Program Files (x86)\Ubisoft\Ubisoft Game Launcher\data\`
- Launch: `uplay://launch/<id>/0`

### Battle.net
- Config: `C:\ProgramData\Battle.net\Agent\product.db` (protobuf)
- Manual scan of common install dirs
- Launch: `battlenet://<product_code>`

### Local Games
- User-configured directories (stored in userdata.json)
- Scan for .exe, .lnk, .url files
- Launch: direct subprocess

### Retro ROMs
- User-configured ROM directories
- Same system support as YancoDeck (25 systems)
- RetroArch Windows: `RetroArch.exe -L cores/<core>.dll <rom>`
- Standalone emulators: PCSX2, Dolphin, PPSSPP, RPCS3, Cemu (Windows .exe)

## Visual Identity

- **Name**: YancoHub
- **Background**: #060b14 (deep dark blue-black)
- **Primary accent**: #00e5c1 (YancoVerse teal)
- **Body text**: #8a9bb0 (muted blue-gray)
- **Titles**: #c8d6e5
- **Aesthetic**: Same as YancoDeck — dark, atmospheric, cinematic, glassmorphism, hexagonal crystal cards
- **Typography**: Inter (web font) or system sans-serif
- **Navigation**: Mouse + keyboard primary, gamepad optional

## API Endpoints

- `GET /health` — Service status
- `GET /api/games?source=steam&system=snes` — Game list with filters
- `GET /api/artwork/<game_id>/<art_type>` — Cover artwork
- `POST /api/launch/<game_id>` — Launch game
- `POST /api/rescan` — Re-scan all libraries
- `GET /api/search?q=<query>` — Search games
- `GET /api/playtime` — Play time data
- `POST /api/collections` — Create collection
- `GET /api/collections` — List collections
- `DELETE /api/collections/<name>` — Delete collection
- `POST /api/collections/<name>/games` — Add game to collection
- `DELETE /api/collections/<name>/games/<game_id>` — Remove from collection
- `GET /api/favorites` — Favorited games
- `POST /api/favorites/toggle` — Toggle favorite
- `GET /api/catbyte/status` — CatByte AI status
- `POST /api/catbyte/chat` — Chat with CatByte
- `GET /api/stores` — Detected store status
- `POST /api/local-dirs` — Add local game directory
- `GET /api/local-dirs` — List local game directories

## Ports

- 8745: Flask backend
- 18789: OpenClaw gateway (CatByte AI)

## Critical Rules

- Windows-only — use Windows registry, paths, shell protocols
- All game stores are optional — app works with zero stores installed
- CatByte (OpenClaw) is optional — app works without AI
- Never block on store scanning — scan async, show results as they come
- Game process tracking via psutil (PID monitoring)
- Artwork caching in cache/artwork/
- All user data in userdata.json (portable)
- Support both mouse+keyboard and gamepad input
