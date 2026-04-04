# YancoHub

**All your games. One place.**

YancoHub is a unified PC game launcher that brings together games from Steam, Epic, GOG, EA, Ubisoft, Battle.net, local games, and retro ROMs into one dark, cinematic interface — with a built-in retro emulator and CatByte AI gaming companion.

![YancoVerse](https://img.shields.io/badge/YancoVerse-00e5c1?style=flat-square) ![Platform](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows) ![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=flat-square&logo=python&logoColor=white)

## Features

### Game Library
- **Multi-store aggregation** — Steam, Epic, GOG, Xbox, EA, Ubisoft, Battle.net
- **Account connection** — Steam Web API for full owned library, GOG Galaxy DB for multi-platform, Epic via legendary
- **Local games** — Scan any directory for game executables
- **Retro ROMs** — 25+ systems with automatic detection

### Built-in Retro Emulator
- **19 systems** run directly inside YancoHub — no external emulator needed
- **Tier 1 (zero setup):** NES, SNES, Game Boy, GBC, GBA, Genesis, Master System, Game Gear, Atari 2600, Neo Geo Pocket, PS1
- **Tier 2 (user BIOS):** Neo Geo, CPS1/2/3, MAME, NDS
- **Tier 3 (beta):** N64
- Cinematic per-system boot sequences
- Save states, screenshots, pause menu
- Powered by [EmulatorJS](https://emulatorjs.org)

### CatByte AI
- Gaming companion powered by [OpenClaw](https://github.com/nicholasgasior/openclaw)
- Ask for tips, walkthroughs, recommendations
- Knows your game library and what you're playing

### UI
- Dark cinematic aesthetic with teal (#00e5c1) accent
- 3D hexagonal crystal carousel with perspective transforms
- Animated starfield with nebulae and floating particles
- Glassmorphism overlays and panels
- Keyboard, mouse, and gamepad navigation

## Quick Start

```bash
git clone https://github.com/YamanAddas/YancoHub.git
cd YancoHub
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python launch.py
```

Or double-click `launch.bat`.

## Requirements

- Python 3.10+
- Windows 10/11

## Configuration

### Connect Steam
1. Get a free API key from [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
2. Open YancoHub → Settings → Connect Steam
3. Paste your API key and Steam ID/profile URL

### Connect Epic (via legendary)
1. `pip install legendary-gl`
2. Open YancoHub → Settings → Epic → Login

### Add ROMs
1. Open YancoHub → Settings → ROM Directories → Add
2. Point to a folder organized by system (e.g., `roms/snes/`, `roms/gba/`)

### BIOS Files
Place BIOS files in the `bios/` directory. See `bios/README.md` for details.
Open-source BIOS for GBA and PS1 are included.

## Architecture

```
launch.py → starts Flask backend (port 8745) + pywebview window
  app.py      — REST API (games, artwork, search, collections, accounts, emulator)
  scanner.py  — game detection (Steam, Epic, GOG, Xbox, EA, Ubisoft, Battle.net, local, ROMs)
  accounts.py — store account connections (Steam API, GOG Galaxy DB, Epic/legendary)
  userdata.py — persistent user data (play time, favorites, collections)
  catbyte.py  — CatByte AI via OpenClaw
  static/     — frontend (HTML, CSS, JS)
  emulator.js — built-in EmulatorJS integration
```

## Part of YancoVerse

YancoHub is the Windows PC counterpart to [YancoDeck](https://github.com/YamanAddas/YancoDeck) (Steam Deck launcher). Same aesthetic, same CatByte AI, different platform.

## License

MIT
