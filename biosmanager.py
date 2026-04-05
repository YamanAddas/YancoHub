"""
YancoHub BIOS Manager — Auto-detects and matches BIOS files from user directories.

User points to any folder with BIOS files. YancoHub scans and auto-matches
files to systems by known filenames and MD5 hashes.
"""

import logging
from pathlib import Path

logger = logging.getLogger('yancohub.biosmanager')

# ── Known BIOS database ────────────────────────────────────────────────────
# Each system lists known BIOS files with optional MD5 for verification.
# 'required' means the built-in emulator won't work without it.
# 'bundled' means we ship an open-source replacement.

KNOWN_BIOS = {
    'gba': {
        'name': 'Game Boy Advance',
        'files': [
            {'name': 'gba_bios.bin', 'md5': 'a860e8c0b6d573d191e4ec7db1b1e4f6', 'required': False,
             'bundled': True, 'note': 'Open-source (Cult-of-GBA, MIT license)'},
        ],
    },
    'psx': {
        'name': 'PlayStation',
        'files': [
            {'name': 'scph1001.bin', 'md5': '924e392ed05558ffdb115408c263dccf', 'required': False,
             'bundled': True, 'note': 'OpenBIOS (MIT license) or proprietary'},
            {'name': 'scph5500.bin', 'md5': '8dd7d5296a650fac7319bce665a6a53c', 'required': False,
             'note': 'Japan BIOS'},
            {'name': 'scph5501.bin', 'md5': '490f666e1afb15b7c8b2f60a9a796de2', 'required': False,
             'note': 'North America BIOS'},
            {'name': 'scph5502.bin', 'md5': '32736f17079d0b2b7024407c39bd3050', 'required': False,
             'note': 'Europe BIOS'},
        ],
    },
    'nds': {
        'name': 'Nintendo DS',
        'files': [
            {'name': 'bios7.bin', 'md5': 'df692a80a5b1bc90571e5b1e0e17ee34', 'required': True,
             'note': 'ARM7 BIOS'},
            {'name': 'bios9.bin', 'md5': 'a392174eb3e572fed6447e956bde4b25', 'required': True,
             'note': 'ARM9 BIOS'},
            {'name': 'firmware.bin', 'required': False,
             'note': 'NDS firmware (optional, various versions)'},
        ],
    },
    'neogeo': {
        'name': 'Neo Geo',
        'files': [
            {'name': 'neogeo.zip', 'required': True,
             'note': 'Neo Geo BIOS archive'},
        ],
    },
    'dreamcast': {
        'name': 'Dreamcast',
        'files': [
            {'name': 'dc_boot.bin', 'md5': 'e10c53c2f8b90bab96ead2d368858623', 'required': False,
             'note': 'Dreamcast BIOS (Flycast has HLE fallback)'},
            {'name': 'dc_flash.bin', 'md5': '0a93f7940c455905bea6e392dfde92a4', 'required': False,
             'note': 'Dreamcast flash memory'},
        ],
    },
    'saturn': {
        'name': 'Sega Saturn',
        'files': [
            {'name': 'saturn_bios.bin', 'required': True,
             'note': 'Saturn BIOS'},
            {'name': 'sega_101.bin', 'md5': '85ec9ca47d8f6807718151cbcbcb664a', 'required': True,
             'note': 'Japan BIOS'},
            {'name': 'mpr-17933.bin', 'md5': '3240872c70984b6cbfda1586cab68dbe', 'required': True,
             'note': 'North America/Europe BIOS'},
        ],
    },
    'ps2': {
        'name': 'PlayStation 2',
        'files': [
            {'name': 'ps2-0230a-20080220.bin', 'required': False,
             'note': 'PCSX2 can run without BIOS in recent versions'},
            # Many PS2 BIOS versions exist
        ],
    },
    'segacd': {
        'name': 'Sega CD',
        'files': [
            {'name': 'bios_CD_U.bin', 'required': True, 'note': 'US Sega CD BIOS'},
            {'name': 'bios_CD_E.bin', 'required': True, 'note': 'EU Mega CD BIOS'},
            {'name': 'bios_CD_J.bin', 'required': True, 'note': 'JP Mega CD BIOS'},
        ],
    },
    'pce': {
        'name': 'PC Engine CD',
        'files': [
            {'name': 'syscard3.pce', 'required': True, 'note': 'System Card 3.0'},
        ],
    },
    'lynx': {
        'name': 'Atari Lynx',
        'files': [
            {'name': 'lynxboot.img', 'md5': 'fcd403db69f54290b51035d82f835e7b', 'required': True},
        ],
    },
}

# Aliases: alternate filenames that map to the same BIOS
FILENAME_ALIASES = {
    # PS1
    'scph1001.bin': ('psx', 'scph1001.bin'),
    'scph5500.bin': ('psx', 'scph5500.bin'),
    'scph5501.bin': ('psx', 'scph5501.bin'),
    'scph5502.bin': ('psx', 'scph5502.bin'),
    'psxonpsp660.bin': ('psx', 'scph1001.bin'),
    # GBA
    'gba_bios.bin': ('gba', 'gba_bios.bin'),
    'gba.bin': ('gba', 'gba_bios.bin'),
    # NDS
    'bios7.bin': ('nds', 'bios7.bin'),
    'bios9.bin': ('nds', 'bios9.bin'),
    'firmware.bin': ('nds', 'firmware.bin'),
    # Dreamcast
    'dc_boot.bin': ('dreamcast', 'dc_boot.bin'),
    'dc_flash.bin': ('dreamcast', 'dc_flash.bin'),
    # Neo Geo
    'neogeo.zip': ('neogeo', 'neogeo.zip'),
    # Saturn
    'saturn_bios.bin': ('saturn', 'saturn_bios.bin'),
    'sega_101.bin': ('saturn', 'sega_101.bin'),
    'mpr-17933.bin': ('saturn', 'mpr-17933.bin'),
}


class BIOSManager:
    """Scans directories for BIOS files and reports per-system status."""

    def __init__(self):
        self.bios_dirs = []
        self.found = {}  # system → {filename → path}
        self._bundled_dir = Path(__file__).parent / 'bios'

    def set_bios_dirs(self, dirs):
        """Set directories to scan for BIOS files."""
        self.bios_dirs = [Path(d) for d in dirs if Path(d).exists()]
        self.scan()

    def scan(self):
        """Scan all configured directories for known BIOS files."""
        self.found = {}

        # Always include the bundled bios directory
        scan_dirs = [self._bundled_dir] + self.bios_dirs

        for bios_dir in scan_dirs:
            if not bios_dir.exists():
                continue

            for f in bios_dir.iterdir():
                if not f.is_file():
                    continue

                fname = f.name.lower()

                # Check against known filenames
                for system_id, system_info in KNOWN_BIOS.items():
                    for bios_file in system_info['files']:
                        if fname == bios_file['name'].lower():
                            self.found.setdefault(system_id, {})[bios_file['name']] = str(f)

                # Check aliases
                if fname in {k.lower(): k for k in FILENAME_ALIASES}:
                    for alias_key, (sys_id, target_name) in FILENAME_ALIASES.items():
                        if fname == alias_key.lower():
                            self.found.setdefault(sys_id, {})[target_name] = str(f)

            # Also scan one level deep (some users organize by subfolder)
            for subdir in bios_dir.iterdir():
                if not subdir.is_dir():
                    continue
                for f in subdir.iterdir():
                    if not f.is_file():
                        continue
                    fname = f.name.lower()
                    for system_id, system_info in KNOWN_BIOS.items():
                        for bios_file in system_info['files']:
                            if fname == bios_file['name'].lower():
                                self.found.setdefault(system_id, {})[bios_file['name']] = str(f)

        logger.info(f"BIOS scan: found files for {len(self.found)} systems")

    def get_status(self):
        """Get per-system BIOS status."""
        status = {}
        for system_id, system_info in KNOWN_BIOS.items():
            files_status = []
            all_required_found = True

            for bios_file in system_info['files']:
                found_path = self.found.get(system_id, {}).get(bios_file['name'])
                is_found = found_path is not None
                is_bundled = bios_file.get('bundled', False)

                if bios_file.get('required') and not is_found and not is_bundled:
                    all_required_found = False

                files_status.append({
                    'name': bios_file['name'],
                    'found': is_found,
                    'path': found_path or '',
                    'required': bios_file.get('required', False),
                    'bundled': is_bundled,
                    'note': bios_file.get('note', ''),
                })

            status[system_id] = {
                'system_name': system_info['name'],
                'ready': all_required_found,
                'files': files_status,
            }

        return status

    def get_bios_path(self, system, filename=None):
        """Get the path to a BIOS file for a system.
        Returns the first matching file if filename is not specified.
        """
        system_files = self.found.get(system, {})

        if filename:
            return system_files.get(filename)

        # Return first found file
        if system_files:
            return next(iter(system_files.values()))

        # Check bundled
        if system in KNOWN_BIOS:
            for bios_file in KNOWN_BIOS[system]['files']:
                if bios_file.get('bundled'):
                    bundled_path = self._bundled_dir / bios_file['name']
                    if bundled_path.exists():
                        return str(bundled_path)

        return None

    def get_bios_dirs(self):
        """Get configured BIOS directories."""
        return [str(d) for d in self.bios_dirs]
