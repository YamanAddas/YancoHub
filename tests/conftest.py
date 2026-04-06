"""
YancoHub Test Configuration — shared fixtures for all test modules.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── Temp directory fixtures ────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a clean temp directory."""
    return tmp_path


@pytest.fixture
def tmp_json(tmp_path):
    """Provide a temp path for JSON files that doesn't exist yet."""
    return tmp_path / 'data.json'


@pytest.fixture
def userdata_instance(tmp_path):
    """UserData backed by a temp file (no side effects on real data)."""
    from userdata import UserData
    ud = UserData(data_file=tmp_path / 'userdata.json')
    yield ud
    ud.flush()


@pytest.fixture
def chat_history_instance(tmp_path):
    """ChatHistory backed by a temp file."""
    from chathistory import ChatHistory
    return ChatHistory(data_file=tmp_path / 'chat_history.json')


@pytest.fixture
def metadata_db(tmp_path):
    """MetadataDB backed by a temp SQLite file."""
    from metadata import MetadataDB
    return MetadataDB(db_path=tmp_path / 'metadata.db')


@pytest.fixture
def bios_manager():
    """Fresh BIOSManager instance."""
    from biosmanager import BIOSManager
    return BIOSManager()


# ── ROM fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def rom_dir(tmp_path):
    """Create a temp directory with synthetic ROM files for testing."""
    roms = tmp_path / 'roms'
    roms.mkdir()
    return roms


def make_snes_rom(path: Path, title: str):
    """Create a minimal SNES ROM with a title at the LoROM header offset."""
    data = bytearray(0x8000)  # 32KB minimum
    # Write title at LoROM offset 0x7FC0 (21 bytes, padded with spaces)
    encoded = title.encode('ascii')[:21].ljust(21, b' ')
    data[0x7FC0:0x7FC0 + 21] = encoded
    path.write_bytes(bytes(data))


def make_gb_rom(path: Path, title: str):
    """Create a minimal GB ROM with a title at 0x134."""
    data = bytearray(0x150)
    encoded = title.encode('ascii')[:15].ljust(15, b'\x00')
    data[0x134:0x143] = encoded
    path.write_bytes(bytes(data))


def make_gba_rom(path: Path, title: str):
    """Create a minimal GBA ROM with a title at 0xA0."""
    data = bytearray(0xC0)
    encoded = title.encode('ascii')[:12].ljust(12, b'\x00')
    data[0xA0:0xAC] = encoded
    path.write_bytes(bytes(data))


def make_genesis_rom(path: Path, title: str):
    """Create a minimal Genesis ROM with overseas name at 0x150."""
    data = bytearray(0x200)
    encoded = title.encode('ascii')[:48].ljust(48, b' ')
    data[0x150:0x180] = encoded
    path.write_bytes(bytes(data))


def make_n64_rom(path: Path, title: str, byte_swap=False):
    """Create a minimal N64 ROM with title at 0x20."""
    data = bytearray(0x40)
    if byte_swap:
        data[0:4] = b'\x37\x80\x40\x12'  # v64 magic
        encoded = title.encode('ascii')[:20].ljust(20, b'\x00')
        # Byte-swap the title
        swapped = bytearray(len(encoded))
        for i in range(0, len(encoded) - 1, 2):
            swapped[i] = encoded[i + 1]
            swapped[i + 1] = encoded[i]
        data[0x20:0x34] = swapped
    else:
        data[0:4] = b'\x80\x37\x12\x40'  # z64 magic
        encoded = title.encode('ascii')[:20].ljust(20, b'\x00')
        data[0x20:0x34] = encoded
    path.write_bytes(bytes(data))
