"""
YancoHub — Emulator Auto-Setup Engine

Downloads and configures RetroArch + cores so users never need to install
emulators manually. Like EmuDeck, but built directly into the launcher.

RetroArch portable is downloaded from the official libretro buildbot.
Individual cores are downloaded on demand based on which ROM systems
the user actually has games for.

All managed emulators live in YancoHub's own `emulators/` directory —
never overwrites system-installed emulators.
"""

import io
import logging
import threading
import time
import zipfile
from pathlib import Path

import py7zr
import requests

from scanner import ROM_SYSTEMS

logger = logging.getLogger('yancohub.emusetup')

# ── Download URLs ──────────────────────────────────────────────────────────

RETROARCH_VERSION = '1.19.1'
RETROARCH_URL = (
    f'https://buildbot.libretro.com/stable/{RETROARCH_VERSION}'
    f'/windows/x86_64/RetroArch.7z'
)
CORE_URL_TEMPLATE = (
    'https://buildbot.libretro.com/nightly/windows/x86_64/latest/{core}.dll.zip'
)

# Systems handled by the built-in browser emulator (EmulatorJS) —
# these do NOT need RetroArch cores
BUILTIN_SYSTEMS = {
    'nes', 'snes', 'gb', 'gbc', 'gba',
    'megadrive', 'mastersystem', 'gamegear',
    'atari2600', 'ngp', 'psx',
    'neogeo', 'fbneo', 'cps1', 'cps2', 'cps3', 'mame',
    'nds', 'n64',
}

# Managed emulator base directory
BASE_DIR = Path(__file__).parent / 'emulators'


class EmulatorSetup:
    """Manages automatic download and configuration of RetroArch + cores."""

    def __init__(self):
        self._ra_dir = BASE_DIR / 'retroarch'
        self._session = requests.Session()
        self._session.headers['User-Agent'] = 'YancoHub/1.0'
        self._lock = threading.Lock()
        self.progress = {
            'active': False,
            'phase': '',
            'current_item': '',
            'downloaded': 0,
            'total': 0,
            'bytes_downloaded': 0,
            'bytes_total': 0,
            'error': None,
            'done': False,
        }

    # ── Status ─────────────────────────────────────────────────────────────

    def get_retroarch_path(self) -> Path | None:
        """Return managed RetroArch dir if installed, else None."""
        exe = self._ra_dir / 'retroarch.exe'
        return self._ra_dir if exe.exists() else None

    def get_status(self, active_systems: list[str]) -> dict:
        """Get install status for all emulators needed by the user's ROM library.

        Args:
            active_systems: system IDs the user actually has ROMs for.
        """
        ra_installed = (self._ra_dir / 'retroarch.exe').exists()
        cores_dir = self._ra_dir / 'cores'

        # Deduplicate: multiple systems can share a core
        needed_cores: dict[str, list[str]] = {}  # core_dll → [system_ids]
        for sys_id in active_systems:
            if sys_id in BUILTIN_SYSTEMS:
                continue
            info = ROM_SYSTEMS.get(sys_id, {})
            core = info.get('core', '')
            if not core:
                continue
            needed_cores.setdefault(core, []).append(sys_id)

        cores_status = {}
        installed_count = 0
        for core_dll, sys_ids in needed_cores.items():
            installed = (cores_dir / core_dll).exists()
            if installed:
                installed_count += 1
            cores_status[core_dll] = {
                'system_ids': sys_ids,
                'system_names': [ROM_SYSTEMS[s]['name'] for s in sys_ids],
                'installed': installed,
            }

        needed = len(needed_cores)
        return {
            'retroarch': {
                'installed': ra_installed,
                'path': str(self._ra_dir) if ra_installed else None,
            },
            'cores': cores_status,
            'needed_count': needed,
            'installed_count': installed_count,
            'ready': ra_installed and installed_count >= needed,
        }

    def get_needed_cores(self, active_systems: set[str]) -> set[str]:
        """Return the set of core DLL names needed for the given systems."""
        cores = set()
        for sys_id in active_systems:
            if sys_id in BUILTIN_SYSTEMS:
                continue
            info = ROM_SYSTEMS.get(sys_id, {})
            core = info.get('core', '')
            if core:
                cores.add(core)
        return cores

    # ── Setup Orchestrator ─────────────────────────────────────────────────

    def setup(self, needed_cores: set[str]):
        """Download RetroArch + needed cores. Run in a background thread.

        Non-destructive: skips already-installed components.
        """
        with self._lock:
            if self.progress.get('active'):
                return
            self.progress = {
                'active': True, 'phase': 'preparing',
                'current_item': '', 'downloaded': 0,
                'total': 0, 'bytes_downloaded': 0,
                'bytes_total': 0, 'error': None, 'done': False,
            }

        try:
            BASE_DIR.mkdir(parents=True, exist_ok=True)

            # Phase 1: RetroArch
            ra_exe = self._ra_dir / 'retroarch.exe'
            cores_to_download = [
                c for c in needed_cores
                if not (self._ra_dir / 'cores' / c).exists()
            ]
            total_items = (0 if ra_exe.exists() else 1) + len(cores_to_download)
            self.progress['total'] = total_items

            if not ra_exe.exists():
                self.progress['phase'] = 'retroarch'
                self.progress['current_item'] = 'RetroArch'
                ok = self._download_retroarch()
                if not ok:
                    return
                self.progress['downloaded'] = 1

            # Phase 2: Cores
            self.progress['phase'] = 'cores'
            failed_cores = []
            for i, core in enumerate(sorted(cores_to_download)):
                if (self._ra_dir / 'cores' / core).exists():
                    self.progress['downloaded'] += 1
                    continue
                self.progress['current_item'] = core
                ok = self._download_core(core)
                if not ok:
                    failed_cores.append(core)
                self.progress['downloaded'] += 1

            # Phase 3: Config
            self.progress['phase'] = 'config'
            self.progress['current_item'] = 'retroarch.cfg'
            self._write_default_config()

            if failed_cores:
                self.progress['error'] = f'Failed to download {len(failed_cores)} core(s): {", ".join(failed_cores)}'
                logger.warning(f"Emulator setup: failed cores: {failed_cores}")

            self.progress['phase'] = 'done'
            logger.info(f"Emulator setup complete: {self.progress['downloaded']}/{total_items} items")

        except Exception as e:
            logger.error(f"Emulator setup failed: {e}")
            self.progress['error'] = str(e)
        finally:
            self.progress['active'] = False
            self.progress['done'] = True

    # ── Downloads ──────────────────────────────────────────────────────────

    def _download_retroarch(self) -> bool:
        """Download and extract RetroArch portable."""
        tmp_path = BASE_DIR / 'RetroArch.7z.tmp'
        try:
            logger.info(f"Downloading RetroArch from {RETROARCH_URL}")
            resp = self._session.get(RETROARCH_URL, stream=True, timeout=30)
            resp.raise_for_status()

            total_bytes = int(resp.headers.get('Content-Length', 0))
            self.progress['bytes_total'] = total_bytes
            self.progress['bytes_downloaded'] = 0

            with open(tmp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    self.progress['bytes_downloaded'] += len(chunk)

            # Extract
            self.progress['current_item'] = 'Extracting RetroArch...'
            self._ra_dir.mkdir(parents=True, exist_ok=True)

            with py7zr.SevenZipFile(str(tmp_path), mode='r') as archive:
                archive.extractall(path=str(self._ra_dir))

            # RetroArch 7z extracts into a subfolder — flatten if needed
            nested = self._ra_dir / 'RetroArch-Win64'
            if not nested.exists():
                nested = self._ra_dir / 'RetroArch'
            if nested.exists() and nested.is_dir():
                import shutil
                for item in nested.iterdir():
                    dest = self._ra_dir / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.copytree(str(item), str(dest), dirs_exist_ok=True)
                        else:
                            item.replace(dest)
                    else:
                        item.rename(dest)
                # Remove empty nested dir
                try:
                    shutil.rmtree(str(nested))
                except Exception:
                    pass

            # Verify
            if not (self._ra_dir / 'retroarch.exe').exists():
                self.progress['error'] = 'RetroArch extraction failed — retroarch.exe not found'
                logger.error("RetroArch extracted but retroarch.exe not found")
                return False

            logger.info(f"RetroArch installed at {self._ra_dir}")
            return True

        except requests.RequestException as e:
            self.progress['error'] = f'Download failed: {e}'
            logger.error(f"RetroArch download failed: {e}")
            return False
        except Exception as e:
            self.progress['error'] = f'Extraction failed: {e}'
            logger.error(f"RetroArch extraction failed: {e}")
            return False
        finally:
            # Clean up temp file
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _download_core(self, core_name: str) -> bool:
        """Download a single RetroArch core from buildbot."""
        cores_dir = self._ra_dir / 'cores'
        cores_dir.mkdir(parents=True, exist_ok=True)

        # Core name: e.g. 'snes9x_libretro.dll' → URL needs 'snes9x_libretro'
        core_stem = core_name.replace('.dll', '')
        url = CORE_URL_TEMPLATE.format(core=core_stem)

        tmp_path = cores_dir / f'{core_name}.zip.tmp'
        try:
            resp = self._session.get(url, stream=True, timeout=20)
            resp.raise_for_status()

            self.progress['bytes_total'] = int(resp.headers.get('Content-Length', 0))
            self.progress['bytes_downloaded'] = 0

            with open(tmp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=32768):
                    f.write(chunk)
                    self.progress['bytes_downloaded'] += len(chunk)

            # Extract DLL from zip
            with zipfile.ZipFile(str(tmp_path), 'r') as zf:
                # Find the .dll inside the zip
                dll_names = [n for n in zf.namelist() if n.endswith('.dll')]
                if not dll_names:
                    logger.warning(f"No .dll found in {core_name}.zip")
                    return False
                zf.extract(dll_names[0], str(cores_dir))
                # If extracted to a subfolder, move it up
                extracted = cores_dir / dll_names[0]
                target = cores_dir / core_name
                if extracted != target:
                    extracted.replace(target)

            logger.debug(f"Core installed: {core_name}")
            return True

        except requests.RequestException as e:
            logger.warning(f"Core download failed ({core_name}): {e}")
            return False
        except Exception as e:
            logger.warning(f"Core extraction failed ({core_name}): {e}")
            return False
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    # ── Configuration ──────────────────────────────────────────────────────

    def _write_default_config(self):
        """Write sensible default RetroArch configuration."""
        cfg_path = self._ra_dir / 'retroarch.cfg'
        if cfg_path.exists():
            return  # Don't overwrite user's config

        saves = self._ra_dir / 'saves'
        states = self._ra_dir / 'states'
        system = self._ra_dir / 'system'
        saves.mkdir(exist_ok=True)
        states.mkdir(exist_ok=True)
        system.mkdir(exist_ok=True)

        config = f"""# YancoHub Auto-Generated RetroArch Configuration
video_fullscreen = "true"
video_windowed_fullscreen = "true"
input_autodetect_enable = "true"
menu_driver = "ozone"
savefile_directory = "{saves}"
savestate_directory = "{states}"
system_directory = "{system}"
input_exit_emulator = "escape"
pause_nonactive = "false"
video_font_enable = "true"
"""
        cfg_path.write_text(config, encoding='utf-8')
        logger.info(f"Wrote default RetroArch config: {cfg_path}")
