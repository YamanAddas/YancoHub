# YancoHub — Known Bugs

Consolidated from full codebase audit (April 2026). Fix in order listed.

---

## CRITICAL — Fix Before First Run

### BUG-001: Command injection via shell=True
**File:** `app.py:276`
**Impact:** Arbitrary command execution from malicious game names/paths
**Details:** `subprocess.Popen(launch_cmd, shell=True, ...)` — shell metacharacters (`;`, `&&`, `|`) in launch_cmd could execute arbitrary commands. Local game paths and ROM filenames are user-controlled.
**Fix:**
```python
import shlex
# For direct exe launches:
args = shlex.split(launch_cmd)
proc = subprocess.Popen(args, shell=False, cwd=...)
# For URL protocols: os.startfile() is already correct
```

### BUG-002: Thread-unsafe global game_library / game_index
**File:** `app.py:59-61, 141-142`
**Impact:** Race conditions serving partially-built library
**Fix:** Atomic swap pattern — see ARCHITECTURE.md "Thread Safety Pattern"

### BUG-003: Thread-unsafe active_process / active_game_id
**File:** `app.py:63-64`
**Impact:** Monitor threads and request handlers race on these globals
**Fix:** Dedicated lock — see ARCHITECTURE.md

### BUG-004: GOG Galaxy DB opened read-write
**File:** `scanner.py:313`
**Impact:** Could corrupt GOG Galaxy's database or trigger lock conflicts
**Fix:** `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`

### BUG-005: GOG Galaxy wrong table name
**File:** `scanner.py:316`
**Impact:** Immediate crash — `InstalledBaseProducts` doesn't exist
**Fix:** Use `LibraryReleases` query pattern from accounts.py, or catch `OperationalError`

---

## HIGH — Broken Functionality

### BUG-006: Epic game ID mismatch
**File:** `scanner.py:247` vs `accounts.py:425`
**Impact:** Installed Epic games never merge with account games — duplicates in library
**Scanner:** `epic_{make_game_id('epic', app_name)}` (MD5 hash)
**Accounts:** `epic_{app_name}` (raw string)
**Fix:** Use `epic_{app_name}` in scanner.py

### BUG-007: GOG game ID mismatch
**File:** `scanner.py:290` vs `accounts.py:312`
**Impact:** Installed GOG games don't merge with Galaxy DB games
**Fix:** Normalize to same ID format (prefer registry GAMEID)

### BUG-008: Emulator session never ends
**File:** `emulator.js:110-112`
**Impact:** active_game_id stuck forever after playing built-in emulator game. Infinite playtime accumulation. CatByte always thinks you're playing that ROM.
**Fix:** Add fetch to `/api/session/end/<game_id>` in `exitEmulator()`

### BUG-009: ACF parsing is fragile
**File:** `scanner.py:162-170`
**Impact:** Nested VDF blocks produce garbage data
**Fix:** Use the `vdf` library (already in requirements.txt) for ACF parsing

### BUG-010: URL monitor unreliable process detection
**File:** `app.py:324-331`
**Impact:** Games named "The Witcher 3" match any process containing "witcher" or "the". "GTA V" matches nothing (all words ≤3 chars skipped). Sessions end prematurely or never.
**Fix:** Timer-based approach with user prompt, or skip process matching entirely

### BUG-011: BIOS route parameter name mismatch
**File:** `app.py:806`
**Impact:** Route uses `<s>` but function parameter is `system` — will crash
**Fix:** Match parameter names: `@app.route('/api/bios/<system>')` or rename function param

### BUG-012: Collection route parameter name mismatch
**File:** `app.py:416-432`
**Impact:** Routes use `<n>` but function params use `name` — will crash
**Fix:** Match parameter names consistently

---

## MEDIUM — Code Quality

### BUG-013: SQLite connections not using context managers
**File:** `metadata.py` (multiple), `scanner.py` GOG scan
**Impact:** Connection leaks on exceptions
**Fix:** Use `with sqlite3.connect(...) as conn:` or try/finally

### BUG-014: No artwork batch timeout
**File:** `artwork.py:282-305`
**Impact:** 100 games × 15s timeout = 25+ minute block on startup
**Fix:** Add overall timeout, or limit concurrent fetches

### BUG-015: Metadata docstring says IGDB, code uses Steam+Wikipedia
**File:** `metadata.py:1-8`
**Impact:** Misleading documentation
**Fix:** Update docstring to match actual implementation

### BUG-016: LIBRETRO_SYSTEMS duplicated
**File:** `metadata.py` and `artwork.py`
**Impact:** Will drift when one is updated
**Fix:** Define once in shared constants module

### BUG-017: catbyte.py imports time inside methods
**File:** `catbyte.py:44, 65, 109-110`
**Impact:** Inconsistent, and line 109 imports as `t` for no reason
**Fix:** Import `time` at module top level

### BUG-018: launch.py uses os.path
**File:** `launch.py` throughout
**Impact:** Inconsistent with pathlib convention
**Fix:** Convert to pathlib.Path

### BUG-019: window.py hardcodes port
**File:** `window.py`
**Impact:** Breaks if FLASK_PORT changes
**Fix:** Import or share the port constant

### BUG-020: formatSize never called
**File:** `app.js:1192`
**Impact:** Dead code
**Fix:** Remove or wire up (e.g., show game install size on cards)

---

## LOW — Polish

### BUG-021: $ helper dual behavior
**File:** `app.js:27`
**Impact:** `$('splash')` tries getElementById then querySelector — confusing fallback
**Fix:** Use only getElementById, create separate `qs()` for selectors

### BUG-022: No CSRF / origin check
**File:** `app.py` — all POST endpoints
**Impact:** Any website can make requests to localhost:8745 and launch games
**Fix:** Check Origin/Referer header, or add secret token

### BUG-023: No launch.bat in repo
**File:** missing
**Impact:** README references it but it doesn't exist
**Fix:** Create it (Phase 1.1 in roadmap)

### BUG-024: art_type not validated
**File:** `app.py:225`
**Impact:** Meaningless cache lookups for invalid art types
**Fix:** Whitelist to `cover`, `header`, `hero`, `logo`, `screenshot`

### BUG-025: Search finds uninstalled games that can't be selected
**File:** `app.js:674-676`
**Impact:** findIndex returns -1, selectedIndex becomes -1
**Fix:** Check idx >= 0 before setting selectedIndex

### BUG-026: 'f' key conflicts with typing
**File:** `app.js:578`
**Impact:** Pressing 'f' toggles favorite when not in an input
**Fix:** Also check for TEXTAREA, SELECT, contenteditable, and whether an overlay is open

### BUG-027: Toggle uninstalled button never initializes
**File:** `app.js:942`
**Impact:** Always shows generic text regardless of state
**Fix:** Fetch current setting and set button text accordingly

### BUG-028: GOG settings section empty
**File:** `index.html:159-162`
**Impact:** Dead `settingsGogGalaxy` div, GOG info renders in `settingsAccounts` instead
**Fix:** Remove dead section or move GOG rendering there

---

## DEPENDENCY

### BUG-029: winshell in requirements but never used
**Fix:** Remove from requirements.txt

### BUG-030: Pillow in requirements but never used
**Fix:** Remove from requirements.txt

### BUG-031: legendary-gl not in requirements
**Impact:** Users don't know to install it for Epic support
**Fix:** Add comment in requirements.txt or document in README

---

## SECURITY

### BUG-032: Steam API key in plaintext JSON
**File:** `userdata.json`
**Impact:** Low (file is gitignored, local-only) but worth noting
**Mitigation:** Document that userdata.json should not be shared

### BUG-033: No path validation on directory endpoints
**File:** `/api/rom-dirs`, `/api/local-dirs`
**Impact:** Could scan system directories
**Fix:** Validate paths are reasonable (not system dirs, exist, are directories)

### BUG-034: send_file on scanner-derived paths
**File:** `app.py:234, 239, 796-800`
**Impact:** Symlinks/junctions in ROM dirs could expose arbitrary files
**Fix:** Validate resolved path is within expected directories

---

**Total: 34 bugs tracked**
**Critical: 5 | High: 7 | Medium: 8 | Low: 8 | Dependency: 3 | Security: 3**
