"""
YancoHub — ROM Identification Engine

Extracts internal game names from ROM binary headers and provides
fuzzy matching against known title databases. This allows artwork
matching even when ROM filenames are mangled, numbered, or abbreviated.

Supported formats:
  SNES (.smc, .sfc)    — internal title at 0x7FC0/0xFFC0, 21 bytes
  N64  (.n64, .z64, .v64) — internal title at 0x20, 20 bytes
  Genesis (.md, .gen)  — overseas name at 0x150, 48 bytes
  GB/GBC (.gb, .gbc)   — title at 0x134, 15 bytes
  GBA (.gba)           — title at 0xA0, 12 bytes (short but useful)
"""

import re
import logging
from pathlib import Path
from difflib import SequenceMatcher

logger = logging.getLogger('yancohub.romident')


# ── ROM Header Readers ─────────────────────────────────────────────────────

def read_rom_header_name(file_path: str, system: str) -> str | None:
    """Extract the internal game name from a ROM's binary header.

    Returns the cleaned title string, or None if unreadable/unsupported.
    """
    reader = _HEADER_READERS.get(system)
    if not reader:
        return None
    try:
        return reader(file_path)
    except Exception as e:
        logger.debug(f"ROM header read failed for {file_path} ({system}): {e}")
        return None


def _read_snes(path: str) -> str | None:
    with open(path, 'rb') as f:
        data = f.read(0x10000)
    if len(data) < 0x8000:
        return None
    # Copier header detection (512 extra bytes)
    offset = 0x200 if (len(data) % 1024 == 512) else 0
    # Try HiROM, then LoROM
    for base in [0xFFC0, 0x7FC0]:
        pos = base + offset
        if pos + 21 > len(data):
            continue
        raw = data[pos:pos + 21]
        name = raw.decode('ascii', errors='ignore').strip('\x00').strip()
        if name and len(name) >= 3 and any(c.isalpha() for c in name):
            return _clean_header_name(name)
    return None


def _read_n64(path: str) -> str | None:
    with open(path, 'rb') as f:
        data = f.read(0x40)
    if len(data) < 0x34:
        return None
    magic = data[0:4]
    raw = data[0x20:0x34]
    if magic == b'\x37\x80\x40\x12':
        # v64 byte-swapped: swap adjacent bytes
        swapped = bytearray(len(raw))
        for i in range(0, len(raw) - 1, 2):
            swapped[i] = raw[i + 1]
            swapped[i + 1] = raw[i]
        raw = bytes(swapped)
    name = raw.decode('ascii', errors='ignore').strip('\x00').strip()
    return _clean_header_name(name) if name and len(name) >= 2 else None


def _read_genesis(path: str) -> str | None:
    with open(path, 'rb') as f:
        data = f.read(0x200)
    if len(data) < 0x190:
        return None
    # Overseas name first (English), then domestic
    for start in [0x150, 0x120]:
        raw = data[start:start + 48]
        name = raw.decode('ascii', errors='ignore').strip('\x00').strip()
        if name and len(name) >= 3 and any(c.isalpha() for c in name):
            return _clean_header_name(name)
    return None


def _read_gb(path: str) -> str | None:
    with open(path, 'rb') as f:
        data = f.read(0x150)
    if len(data) < 0x143:
        return None
    raw = data[0x134:0x143]
    name = raw.decode('ascii', errors='ignore').strip('\x00').strip()
    return _clean_header_name(name) if name and len(name) >= 2 else None


def _read_gba(path: str) -> str | None:
    with open(path, 'rb') as f:
        data = f.read(0xC0)
    if len(data) < 0xAC:
        return None
    raw = data[0xA0:0xAC]
    name = raw.decode('ascii', errors='ignore').strip('\x00').strip()
    return _clean_header_name(name) if name and len(name) >= 3 else None


_HEADER_READERS = {
    'snes': _read_snes,
    'nes': None,          # iNES has no title field
    'gba': _read_gba,
    'gb': _read_gb,
    'gbc': _read_gb,
    'n64': _read_n64,
    'megadrive': _read_genesis,
    'mastersystem': None,  # no standard title header
    'gamegear': None,
    'atari2600': None,
    'famicom': None,
    'fds': None,
}


def _clean_header_name(name: str) -> str:
    """Clean up a raw ROM header name for matching."""
    # Remove trailing garbage (non-printable, symbols from padding)
    name = re.sub(r'[\x00-\x1f\x7f-\xff]+', '', name)
    # Collapse whitespace
    name = ' '.join(name.split())
    return name if name else None


# ── Fuzzy Title Matching ───────────────────────────────────────────────────

def fuzzy_match(query: str, candidates: dict[str, str],
                threshold: float = 0.6) -> str | None:
    """Find the best fuzzy match for `query` in a {normalized_key: value} dict.

    Uses SequenceMatcher ratio on normalized forms. Returns the matched value
    or None if below threshold.

    Performance: filters by first-word overlap before expensive ratio calc.
    Typically compares ~5-15% of candidates instead of 100%.
    """
    if not query or not candidates:
        return None

    query_norm = _normalize_for_fuzzy(query)
    if not query_norm or len(query_norm) < 3:
        return None

    qwords = set(query_norm.split())
    qlen = len(query_norm)
    best_score = 0.0
    best_value = None

    for key, value in candidates.items():
        klen = len(key)
        if klen == 0:
            continue
        # Quick length filter
        if abs(klen - qlen) / max(klen, qlen) > 0.5:
            continue
        # Quick word overlap filter — must share at least one word
        kwords = set(key.split())
        if not qwords & kwords:
            continue

        score = SequenceMatcher(None, query_norm, key).ratio()
        if score > best_score:
            best_score = score
            best_value = value

    if best_score >= threshold:
        return best_value
    return None


def strip_numbering(name: str) -> str:
    """Remove common ROM naming prefixes like '001 ', '000 '."""
    return re.sub(r'^\d{2,4}\s+', '', name)


def _normalize_for_fuzzy(name: str) -> str:
    """Normalize a name for fuzzy comparison."""
    n = name.lower()
    n = re.sub(r'\s*[\(\[].*?[\)\]]', '', n)   # strip tags
    n = n.replace('-', ' ').replace('_', ' ').replace("'", '').replace('&', 'and')
    n = re.sub(r'[^a-z0-9 ]', '', n)
    return ' '.join(n.split())
