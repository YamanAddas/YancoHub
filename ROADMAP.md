# YancoHub — Roadmap

Ordered execution plan. Each phase must be completed and verified before moving to the next. Items within a phase can be done in any order.

---

## Phase 0 — Critical Fixes (COMPLETE)

> All Phase 0 items resolved — see BUGS.md BUG-001 through BUG-049.

These were bugs that would cause crashes, security issues, or data corruption.

### 0.1 — Command injection fix
- `app.py:276`: Replace `shell=True` with `shell=False` + argument list parsing
- For emulator launch commands built as strings with quotes, use `shlex.split()` or parse into list
- For URL protocol launches (`steam://`, etc.), keep `os.startfile()` — that's correct

### 0.2 — Thread safety
- Add `_library_lock = threading.Lock()` for `game_library` / `game_index`
- Add `_active_lock = threading.Lock()` for `active_process` / `active_game_id`
- Use atomic swap pattern in `_build_library()` (build into locals, assign under lock)
- Wrap all reads of `active_game_id` and `active_process` in lock

### 0.3 — GOG Galaxy DB fixes
- scanner.py:313 — Open with `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`
- scanner.py:316 — Replace `InstalledBaseProducts` query with correct tables (`LibraryReleases` pattern from accounts.py)
- Or: catch `sqlite3.OperationalError` gracefully and fall back to registry-only

### 0.4 — Game ID mismatches
- Epic: Change scanner.py to use `epic_{app_name}` instead of `epic_{make_game_id('epic', app_name)}`
- GOG: Ensure scanner and accounts use the same ID format (prefer registry GAMEID)

### 0.5 — Emulator session end
- Add `POST /api/session/end/<game_id>` endpoint to app.py
- In emulator.js `exitEmulator()`: call `fetch('/api/session/end/' + emuGameId, {method:'POST'})` before clearing state
- Endpoint calls `userdata.session_end(game_id)` and clears `active_game_id`

### 0.6 — SQLite context managers
- metadata.py: Wrap all `sqlite3.connect()` calls in `with` statements or try/finally
- scanner.py GOG scan: Same treatment
- accounts.py: Already uses some, verify all paths

---

## Phase 1 — First Run Polish

Make the app actually bootable and pleasant on first launch.

### 1.1 — launch.bat
- Create `launch.bat` that auto-creates venv if missing, installs deps, runs launch.py
- Handle Python not being in PATH gracefully (try `py`, `python3`, `python`)

### 1.2 — Scan completion signal
- Add a `scan_complete` flag or event
- `/api/games` should return `{"status": "scanning", "games": []}` if scan hasn't completed
- Frontend should show a loading state instead of empty carousel during initial scan

### 1.3 — Empty state UX
- When game library is empty, show helpful onboarding: "Add ROM directories or connect a store account in Settings"
- Don't show a blank carousel

### 1.4 — Artwork loading states
- Add shimmer/skeleton placeholder while artwork loads
- Handle `onerror` on images — show the system-colored gradient fallback

### 1.5 — CatByte offline handling
- If CatByte is offline at startup, dim/hide the CatByte button instead of showing a dead panel
- Show a tooltip: "CatByte requires an AI backend — see Settings"

### 1.6 — Cleanup unused dependencies
- Remove `winshell` from requirements.txt (never imported)
- Remove `Pillow` from requirements.txt (never imported)
- Add comment about `legendary-gl` being optional for Epic support

---

## Phase 2 — Visual Excellence

This is where YancoHub must beat Playnite. The UI should feel like a AAA game menu, not a utility app.

### 2.1 — Artwork cache headers
- Add `Cache-Control: public, max-age=86400` to artwork responses
- Eliminates re-fetching on every carousel render

### 2.2 — Carousel animation refinement
- Smooth card entry/exit transitions (currently instant for new cards)
- Subtle breathing glow on the center card
- Magnetic snap feel — slight overshoot and settle on navigation

### 2.3 — Game detail panel
- When a game is centered, show a cinematic detail view:
  - Hero art as blurred background behind the carousel
  - Description text (from metadata)
  - Quick-action buttons: Launch, Favorite, Add to Collection
- Animate the transition: hero art fades in, info slides up

### 2.4 — Splash screen polish
- Add YancoHub logo/wordmark to splash
- Smooth progress bar with per-phase messages
- Fade transition to main app should feel cinematic (not just opacity)

### 2.5 — Settings redesign
- Current settings is a simple overlay with inputs
- Redesign as a proper multi-tab settings panel (Accounts | Directories | Emulation | About)
- Each section should feel polished, not like a debug menu

### 2.6 — Sound design (optional, user-togglable)
- Subtle UI sounds: carousel navigation tick, launch whoosh, tab switch
- Use Web Audio API — no heavy audio files
- Default OFF, toggle in settings

---

## Phase 3 — Gamepad Support

Critical for couch/TV use. This is what makes Playnite's fullscreen mode popular.

### 3.1 — Gamepad API integration
- Use the browser Gamepad API in app.js
- D-pad / left stick → carousel navigation
- A/Enter → launch
- B/Escape → back/close overlay
- Start → settings
- Select → search
- Y → favorite toggle
- Bumpers → tab switching

### 3.2 — Gamepad indicator
- Show connected gamepad icon in the UI
- Support Xbox, PlayStation, and generic controllers
- Show correct button glyphs based on detected controller type

### 3.3 — Focus management
- All interactive elements must be reachable via gamepad
- Settings panel needs gamepad-navigable focus system
- Search overlay needs virtual keyboard or at minimum gamepad-friendly text input

---

## Phase 4 — Platform Depth

### 4.1 — Improved process monitoring
- Replace the name-matching URL monitor with a smarter approach
- Option A: Track the store launcher process (e.g., Steam's game overlay)
- Option B: Timer-based with "Still playing?" UI prompt
- Option C: Window title monitoring via pywebview hooks

### 4.2 — IGDB metadata integration
- Add IGDB API as primary metadata source (more complete than Steam Store API)
- Requires Twitch OAuth client ID (free)
- Fall back to Steam Store API → Wikipedia

### 4.3 — SteamGridDB API for artwork
- Add SteamGridDB as a high-priority artwork source (better community art than Steam CDN)
- Requires free API key
- Great coverage for non-Steam and retro games

### 4.4 — Incremental scan
- Don't re-scan everything when one ROM dir is added
- Track what was scanned and only scan deltas
- Use file modification timestamps to detect changes

### 4.5 — Stale cache cleanup
- Periodically remove artwork for games no longer in library
- Track cache size and offer manual cleanup in settings

---

## Phase 5 — Differentiators

Features that make YancoHub unique — things no competitor does.

### 5.1 — CatByte game awareness
- Pass current game metadata to CatByte (genre, system, description)
- CatByte can give contextual tips, trivia, and recommendations
- "What other [genre] games do I have?" queries against the library

### 5.2 — Smart collections
- Auto-generated collections: "Recently Played", "Most Played", "Unfinished", "By Genre"
- User can pin these to tabs

### 5.3 — Play statistics dashboard
- Total playtime, games played this week/month, streak tracking
- Per-store breakdown
- Most played games chart
- Accessible from a stats tab or overlay

### 5.4 — Cross-session game notes
- Per-game notes field (where was I, what quest, what build)
- Stored in userdata.json
- Visible in the game detail panel

### 5.5 — Import/Export
- Export library list as JSON/CSV
- Import game list from Playnite/LaunchBox XML
- Useful for users migrating from competitors

---

## Phase 6 — Distribution & Quality

### 6.1 — PyInstaller packaging (COMPLETE)
- ~~Create a standalone .exe that bundles Python + deps~~
- ~~MSI/NSIS installer with YancoHub branding~~

### 6.2 — Test suite (COMPLETE)
- ~~183 pytest tests covering constants, ROM parsing, user data, BIOS scanning, chat history, metadata, and Flask routes~~
- ~~Synthetic ROM fixtures, mocked HTTP, temp file isolation — no side effects~~
- ~~Run: `python -m pytest tests/ -v`~~

### 6.3 — Auto-update mechanism
- Check GitHub releases for new versions
- Download and apply updates (or prompt user)

### 6.4 — GitHub release pipeline
- GitHub Actions: lint → test → build → release
- Run `pytest` in CI on every push/PR
- Auto-generate changelog from commit messages

---

## Not Planned (Intentional Omissions)

- **Social features** — this is a personal cockpit, not a social network
- **Store purchasing** — we aggregate, we don't sell
- **Cloud sync** — userdata.json is local-only by design
- **Mobile app** — YancoHub is Windows-only by design
- **Plugin system** — keep it simple; built-in integrations only
- **Achievements** — would require per-store API auth that's fragile
