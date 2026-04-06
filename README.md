# YancoHub

**All your games. One place. No clutter.**

YancoHub is a unified PC game launcher that aggregates Steam, Epic, GOG, Xbox, EA, Ubisoft, Battle.net, local games, and retro ROMs into one dark cinematic interface — with a built-in retro emulator and CatByte AI gaming companion.

![YancoVerse](https://img.shields.io/badge/YancoVerse-00e5c1?style=flat-square) ![Platform](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows) ![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=flat-square&logo=python&logoColor=white) ![License](https://img.shields.io/badge/MIT-green?style=flat-square)

## Why YancoHub

| | Playnite | LaunchBox | GOG Galaxy | **YancoHub** |
|---|---|---|---|---|
| Free & open source | ✅ | ❌ ($30-75) | ❌ | ✅ |
| Multi-store aggregation | ✅ | ✅ | ✅ | ✅ (8 stores) |
| Built-in retro emulator | ❌ (needs RetroArch) | ❌ (needs emulators) | ❌ | ✅ (19 systems) |
| AI gaming companion | ❌ | ❌ | ❌ | ✅ (CatByte) |
| Lightweight (no .NET/WPF) | ❌ | ❌ | N/A | ✅ |
| Cinematic 3D UI | ❌ | Themes only | ❌ | ✅ |

## Features

### Game Library
- **8 stores** — Steam, Epic, GOG, Xbox/Game Pass, EA, Ubisoft, Battle.net
- **Account sync** — Steam Web API (full owned library), GOG Galaxy DB (multi-platform), Epic catalog cache (automatic)
- **Local games** — Scan any directory for executables
- **Retro ROMs** — 25 systems with auto-detection and deduplication

### Built-in Retro Emulator
- **19 systems** run directly in-app via EmulatorJS — no external emulator needed
- **Tier 1 (zero setup):** NES, SNES, GB, GBC, GBA, Genesis, Master System, Game Gear, Atari 2600, Neo Geo Pocket, PS1
- **Tier 2 (user BIOS):** Neo Geo, CPS1/2/3, MAME, NDS
- **Tier 3 (beta):** N64
- Cinematic per-system boot sequences, save states, screenshots, glassmorphism pause menu

### CatByte AI
- Gaming companion with multiple AI backend options (Ollama, LM Studio, OpenAI, OpenClaw, or any OpenAI-compatible endpoint)
- Ask for tips, walkthroughs, recommendations
- Aware of your current game and library
- Screenshot analysis for stuck moments

### Interface
- Dark cinematic aesthetic with teal (#00e5c1) accent
- 3D hexagonal crystal carousel with perspective transforms
- Animated starfield with nebulae and floating particles
- Glassmorphism panels and overlays
- Keyboard, mouse, and gamepad navigation

## Configuration

### Connect Steam
1. Get a free API key: [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
2. Settings → Accounts → Connect Steam → paste API key + Steam ID/profile URL

### Connect Epic
Epic games are detected automatically from the Epic Games Launcher's local catalog cache — just log in to the Epic Launcher and your owned games will appear in YancoHub. No extra tools needed.

### Add ROMs
Settings → Directories → ROM Directories → Add a folder organized by system (e.g., `roms/snes/`, `roms/gba/`)

### BIOS
Place BIOS files in `bios/` directory. Open-source GBA and PS1 BIOS included. See `bios/README.md`.

## Download

### Option A: Installer (recommended)
Download `YancoHub-x.x.x-setup.exe` from [Releases](https://github.com/YamanAddas/YancoHub/releases). Installs to your AppData, creates Start Menu and Desktop shortcuts, and adds an uninstaller to Add/Remove Programs.

### Option B: Portable (no install)
Download `YancoHub-x.x.x-portable.zip` from [Releases](https://github.com/YamanAddas/YancoHub/releases). Extract anywhere and run `YancoHub.exe`. All data stays in the same folder — perfect for USB drives or restricted machines.

### Option C: From source
```bash
git clone https://github.com/YamanAddas/YancoHub.git
cd YancoHub
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python launch.py
```

**Requirements (from source):** Python 3.10+, Windows 10/11

## Building from Source

```bash
pip install pyinstaller
python build.py              # Build both installer and portable zip
python build.py --portable   # Portable zip only
python build.py --installer  # NSIS installer only (requires NSIS on PATH)
```

Output goes to `dist/`. The NSIS installer requires [NSIS 3.x](https://nsis.sourceforge.io/) to be installed and on your PATH.

## Security Note

`userdata.json` stores your settings, including your Steam API key. This file is gitignored and local-only — **do not share it** or commit it to version control.

## Part of YancoVerse

YancoHub is the Windows PC counterpart to [YancoDeck](https://github.com/YamanAddas/YancoDeck) (Steam Deck launcher). Same aesthetic, same CatByte AI.

## License

MIT
