# YancoHub — Known Bugs

Consolidated from full codebase audit (April 2026). Updated April 2026.

**All 66 tracked bugs have been resolved.**

---

## FIXED

| ID | Issue | Resolution |
|----|-------|------------|
| BUG-001 | Command injection via `shell=True` | Uses `shlex.split()` + `shell=False` |
| BUG-002 | Thread-unsafe `game_library`/`game_index` | `_library_lock` with atomic swap |
| BUG-003 | Thread-unsafe `active_process`/`active_game_id` | `_active_lock` with getter/setter |
| BUG-004 | GOG Galaxy DB opened read-write | `?mode=ro` URI |
| BUG-005 | GOG Galaxy wrong table name | Uses `LibraryReleases` |
| BUG-006 | Epic game ID mismatch (scanner vs accounts) | Both use `epic_{app_name}` |
| BUG-007 | GOG game ID mismatch | Consistent format |
| BUG-008 | Emulator session never ends | `exitEmulator()` calls `/api/session/end` |
| BUG-009 | ACF parsing fragile (manual) | Uses `vdf` library |
| BUG-010 | URL monitor unreliable process detection | Process-snapshot diffing instead of name matching |
| BUG-011 | BIOS route parameter mismatch | `<system>` matches function param |
| BUG-012 | Collection route parameter mismatch | `<name>` matches function param |
| BUG-013 | SQLite connections not using context managers | All use `with` or try/finally |
| BUG-014 | No artwork batch timeout | `max_fetch=200`, `timeout=300s` limits |
| BUG-015 | Metadata docstring says IGDB | Updated to match actual sources (Steam+Wikipedia) |
| BUG-016 | LIBRETRO_SYSTEMS duplicated | Single source in `constants.py` |
| BUG-017 | catbyte.py imports time inside methods | Top-level import |
| BUG-018 | launch.py uses os.path | Converted to pathlib |
| BUG-019 | window.py hardcodes port | Imports `FLASK_PORT` from constants |
| BUG-020 | formatSize never called | Removed dead code |
| BUG-021 | `$` helper dual behavior | `$` = getElementById only, added `qs()` for selectors |
| BUG-022 | No CSRF/origin check | `@before_request` origin validation |
| BUG-023 | No launch.bat in repo | Created with auto-venv and dep install |
| BUG-024 | art_type not validated | Allowlist via `VALID_ART_TYPES` |
| BUG-025 | Search finds uninstalled games | `idx >= 0` check before navigating |
| BUG-026 | 'f' key conflicts with typing | Checks overlay state + input focus |
| BUG-027 | Toggle uninstalled button never initializes | Fetches setting via GET endpoint |
| BUG-028 | GOG settings section empty | Dead div already removed from template |
| BUG-029 | winshell in requirements unused | Removed |
| BUG-030 | Pillow in requirements unused | Removed |
| BUG-031 | legendary-gl not in requirements | Comment added noting it's optional |
| BUG-032 | Steam API key in plaintext JSON | Security note added to README |
| BUG-033 | No path validation on directory endpoints | `_validate_dir_path()` blocks system dirs |
| BUG-034 | send_file on scanner-derived paths | `_validate_file_within_dirs()` checks allowed dirs |

---

## Round 2 Audit — FIXED

| ID | Issue | Resolution |
|----|-------|------------|
| BUG-035 | `request.get_json()` returns None when Content-Type missing | All POST endpoints guard with `or {}` |
| BUG-036 | Path traversal in `/assets/audio/<filename>` | `is_relative_to` check before serving |
| BUG-037 | Silent except blocks in Epic manifest parsing | Added `logger.debug()`/`logger.error()` |
| BUG-038 | TOCTOU race on `send_file` for artwork/ROM/BIOS | Wrapped in `try/except FileNotFoundError → abort(404)` |
| BUG-039 | Registry key handles leaked in `get_detected_stores()` | Assigned to variable + `CloseKey()` |
| BUG-040 | Bare except in scanner `_get_steam_path` and GOG GamePieces | Added logging |
| BUG-041 | Unused `import glob` in scanner.py | Removed |
| BUG-042 | SQLite connection leaks in accounts.py | All use `with sqlite3.connect(...)` context manager |
| BUG-043 | Bare except in `get_recently_played` / `resolve_steam_vanity_url` | Added `logger.debug()` with exception info |
| BUG-044 | `userdata.py` mutations not thread-safe | Added `threading.Lock` around all mutating methods |
| BUG-045 | XSS in `data-id` attribute (search results) | Uses `escapeAttr()` on game IDs |
| BUG-046 | Unused `import os` in artwork.py, metadata.py, biosmanager.py | Removed |
| BUG-047 | Unused `import hashlib` in biosmanager.py | Removed |
| BUG-048 | biosmanager.py logger named `yancohub.bios` | Renamed to `yancohub.biosmanager` |
| BUG-049 | catbyte.py hardcoded OpenClaw port 18789 | Imports `OPENCLAW_PORT` from constants |

---

---

## Round 3 Audit — FIXED

| ID | Issue | Resolution |
|----|-------|------------|
| BUG-050 | Dead `SteamAccount.get_recently_played()` | Removed |
| BUG-051 | Dead `UserData.get_active_game()` | Removed (app.py uses `_get_active()`) |
| BUG-052 | Dead `MetadataDB.get_artwork()`/`put_artwork()`/`artwork_cache` table | Removed methods and table creation |
| BUG-053 | Dead `MetadataDB.get_stats()` | Removed |
| BUG-054 | Unused `LIBRETRO_THUMB_BASE`/`STEAM_CDN` in metadata.py | Removed; canonical copies in constants.py |
| BUG-055 | `BUILTIN_SYSTEMS` duplicated in app.py + emusetup.py | Consolidated to constants.py |
| BUG-056 | `STEAM_CDN`/`LIBRETRO_THUMB` duplicated across files | Consolidated to constants.py |
| BUG-057 | `STEAM_CDN` hardcoded inline in accounts.py | Now imports from constants.py |
| BUG-058 | 7 unwired API endpoints with no frontend consumers | Removed (`/api/active-game`, `/api/last-played`, `/api/accounts/epic/status`, `/api/metadata/<game_id>`, `/api/metadata/stats`, `/api/emulator/info/<system>`, `/assets/audio/<filename>`) |
| BUG-059 | Empty stale `static/img/systems/` directory | Deleted |
| BUG-060 | Unused `import sys` in app.py | Removed |
| BUG-061 | Unused `from constants import LIBRETRO_SYSTEMS` in metadata.py | Removed |
| BUG-062 | Unused `import time` in emusetup.py | Removed |
| BUG-063 | 5 dead HTML element IDs never referenced by JS | Removed IDs from elements |
| BUG-064 | 9 dead CSS selectors never used in HTML or JS | Removed |
| BUG-065 | `pywin32` in requirements.txt but never imported | Removed |
| BUG-066 | CLAUDE.md module table missing 5 modules | Added chathistory, emusetup, romident, launch, window |

---

**Total: 66 bugs tracked — 66 fixed, 0 open**
