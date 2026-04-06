"""
YancoHub — Shared Constants
Single source of truth for values used across multiple modules.
"""

# App version — used in User-Agent, About screen, packaging
VERSION = '1.0.0'

# Flask backend port
FLASK_PORT = 8745

# LibRetro system directory names — used by metadata.py and artwork.py
LIBRETRO_SYSTEMS = {
    'nes':          'Nintendo - Nintendo Entertainment System',
    'snes':         'Nintendo - Super Nintendo Entertainment System',
    'gb':           'Nintendo - Game Boy',
    'gbc':          'Nintendo - Game Boy Color',
    'gba':          'Nintendo - Game Boy Advance',
    'n64':          'Nintendo - Nintendo 64',
    'nds':          'Nintendo - Nintendo DS',
    'megadrive':    'Sega - Mega Drive - Genesis',
    'mastersystem': 'Sega - Master System - Mark III',
    'gamegear':     'Sega - Game Gear',
    'atari2600':    'Atari - 2600',
    'psx':          'Sony - PlayStation',
    'ps2':          'Sony - PlayStation 2',
    'psp':          'Sony - PlayStation Portable',
    'dreamcast':    'Sega - Dreamcast',
    'saturn':       'Sega - Saturn',
    'gamecube':     'Nintendo - GameCube',
    'wii':          'Nintendo - Wii',
    'neogeo':       'SNK - Neo Geo',
    'ngp':          'SNK - Neo Geo Pocket',
    'fbneo':        'FBNeo - Arcade Games',
    'cps1':         'FBNeo - Arcade Games',
    'cps2':         'FBNeo - Arcade Games',
    'cps3':         'FBNeo - Arcade Games',
    'mame':         'MAME',
    'atari5200':    'Atari - 5200',
    'atari7800':    'Atari - 7800',
    'atarilynx':    'Atari - Lynx',
    'atarist':      'Atari - ST',
    'atarijaguar':  'Atari - Jaguar',
    'colecovision': 'Coleco - ColecoVision',
    'c64':          'Commodore - 64',
    'amiga':        'Commodore - Amiga',
    'dos':          'DOS',
    'pcengine':     'NEC - PC Engine - TurboGrafx 16',
    'famicom':      'Nintendo - Nintendo Entertainment System',
    'fds':          'Nintendo - Family Computer Disk System',
    'channelf':     'Fairchild - Channel F',
    'arcade':       'FBNeo - Arcade Games',
    'atomiswave':   'Sega - Dreamcast',
    'daphne':       'Daphne',
    'gameandwatch': 'Handheld Electronic Game',
    'odyssey2':     'Magnavox - Odyssey2',
    'vectrex':      'GCE - Vectrex',
    'wonderswan':   'Bandai - WonderSwan',
    'wonderswanc':  'Bandai - WonderSwan Color',
    'intellivision':'Mattel - Intellivision',
    '3do':          'The 3DO Company - 3DO',
}

# Valid artwork types for API validation
VALID_ART_TYPES = {'cover', 'header', 'hero', 'logo', 'screenshot'}

# Steam CDN base URL for app assets
STEAM_CDN = 'https://cdn.cloudflare.steamstatic.com/steam/apps'

# LibRetro thumbnail CDN base URL
LIBRETRO_THUMB = 'https://thumbnails.libretro.com'

# Systems handled by the built-in browser emulator (EmulatorJS) —
# these do NOT need RetroArch cores
BUILTIN_SYSTEMS = {
    'nes', 'snes', 'gb', 'gbc', 'gba',
    'megadrive', 'mastersystem', 'gamegear',
    'atari2600', 'ngp', 'psx',
    'neogeo', 'fbneo', 'cps1', 'cps2', 'cps3', 'mame',
    'nds', 'n64',
}
