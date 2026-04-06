"""Tests for romident.py — ROM header parsing and fuzzy title matching."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import make_snes_rom, make_gb_rom, make_gba_rom, make_genesis_rom, make_n64_rom
from romident import (
    read_rom_header_name,
    fuzzy_match,
    strip_numbering,
    _normalize_for_fuzzy,
    _clean_header_name,
)


class TestSNESHeaderReader:
    def test_lorom_title(self, rom_dir):
        rom = rom_dir / 'game.sfc'
        make_snes_rom(rom, 'SUPER MARIO WORLD')
        result = read_rom_header_name(str(rom), 'snes')
        assert result is not None
        assert 'SUPER MARIO WORLD' in result

    def test_short_file_returns_none(self, rom_dir):
        rom = rom_dir / 'tiny.sfc'
        rom.write_bytes(b'\x00' * 100)
        assert read_rom_header_name(str(rom), 'snes') is None

    def test_empty_title_returns_none(self, rom_dir):
        rom = rom_dir / 'blank.sfc'
        data = bytearray(0x8000)
        rom.write_bytes(bytes(data))
        assert read_rom_header_name(str(rom), 'snes') is None


class TestGBHeaderReader:
    def test_gb_title(self, rom_dir):
        rom = rom_dir / 'game.gb'
        make_gb_rom(rom, 'POKEMON RED')
        result = read_rom_header_name(str(rom), 'gb')
        assert result is not None
        assert 'POKEMON RED' in result

    def test_gbc_uses_same_reader(self, rom_dir):
        rom = rom_dir / 'game.gbc'
        make_gb_rom(rom, 'ZELDA DX')
        result = read_rom_header_name(str(rom), 'gbc')
        assert result is not None
        assert 'ZELDA DX' in result

    def test_short_file_returns_none(self, rom_dir):
        rom = rom_dir / 'tiny.gb'
        rom.write_bytes(b'\x00' * 50)
        assert read_rom_header_name(str(rom), 'gb') is None


class TestGBAHeaderReader:
    def test_gba_title(self, rom_dir):
        rom = rom_dir / 'game.gba'
        make_gba_rom(rom, 'METROID FUSI')
        result = read_rom_header_name(str(rom), 'gba')
        assert result is not None
        assert 'METROID' in result

    def test_short_title_rejected(self, rom_dir):
        """GBA titles under 3 chars are rejected."""
        rom = rom_dir / 'short.gba'
        make_gba_rom(rom, 'AB')
        assert read_rom_header_name(str(rom), 'gba') is None


class TestGenesisHeaderReader:
    def test_genesis_overseas_name(self, rom_dir):
        rom = rom_dir / 'game.md'
        make_genesis_rom(rom, 'SONIC THE HEDGEHOG')
        result = read_rom_header_name(str(rom), 'megadrive')
        assert result is not None
        assert 'SONIC' in result

    def test_short_file_returns_none(self, rom_dir):
        rom = rom_dir / 'tiny.md'
        rom.write_bytes(b'\x00' * 100)
        assert read_rom_header_name(str(rom), 'megadrive') is None


class TestN64HeaderReader:
    def test_z64_title(self, rom_dir):
        rom = rom_dir / 'game.z64'
        make_n64_rom(rom, 'ZELDA MASTER QUEST')
        result = read_rom_header_name(str(rom), 'n64')
        assert result is not None
        assert 'ZELDA' in result

    def test_v64_byte_swapped(self, rom_dir):
        rom = rom_dir / 'game.v64'
        make_n64_rom(rom, 'MARIO 64', byte_swap=True)
        result = read_rom_header_name(str(rom), 'n64')
        assert result is not None
        assert 'MARIO' in result

    def test_short_file_returns_none(self, rom_dir):
        rom = rom_dir / 'tiny.n64'
        rom.write_bytes(b'\x00' * 10)
        assert read_rom_header_name(str(rom), 'n64') is None


class TestUnsupportedSystems:
    def test_unsupported_system_returns_none(self, rom_dir):
        rom = rom_dir / 'game.rom'
        rom.write_bytes(b'\x00' * 1000)
        assert read_rom_header_name(str(rom), 'atari2600') is None

    def test_unknown_system_returns_none(self, rom_dir):
        rom = rom_dir / 'game.rom'
        rom.write_bytes(b'\x00' * 1000)
        assert read_rom_header_name(str(rom), 'unknown_system') is None


class TestCleanHeaderName:
    def test_strips_non_printable(self):
        assert _clean_header_name('HELLO\x00\x01WORLD') == 'HELLOWORLD'

    def test_collapses_whitespace(self):
        assert _clean_header_name('HELLO   WORLD') == 'HELLO WORLD'

    def test_empty_after_cleaning_returns_none(self):
        assert _clean_header_name('\x00\x01\x02') is None


class TestNormalizeForFuzzy:
    def test_lowercase(self):
        assert _normalize_for_fuzzy('HELLO') == 'hello'

    def test_strips_parenthetical_tags(self):
        result = _normalize_for_fuzzy('Super Mario World (USA)')
        assert 'usa' not in result
        assert 'super mario world' in result

    def test_strips_bracket_tags(self):
        result = _normalize_for_fuzzy('Zelda [Rev A]')
        assert 'rev a' not in result

    def test_replaces_separators(self):
        result = _normalize_for_fuzzy("Crash-Bandicoot_2 N'Sane")
        assert '-' not in result
        assert '_' not in result
        assert "'" not in result

    def test_ampersand_to_and(self):
        result = _normalize_for_fuzzy('Ratchet & Clank')
        assert 'and' in result


class TestStripNumbering:
    def test_removes_leading_numbers(self):
        assert strip_numbering('001 Super Mario') == 'Super Mario'
        assert strip_numbering('0042 Zelda') == 'Zelda'

    def test_preserves_no_prefix(self):
        assert strip_numbering('Super Mario') == 'Super Mario'

    def test_single_digit_not_stripped(self):
        """Single digit prefix is NOT a numbering prefix (needs 2+ digits)."""
        assert strip_numbering('1 Game') == '1 Game'


class TestFuzzyMatch:
    def test_exact_match(self):
        candidates = {'super mario world': 'Super Mario World'}
        assert fuzzy_match('Super Mario World', candidates) == 'Super Mario World'

    def test_close_match(self):
        candidates = {'super mario world': 'SMW'}
        result = fuzzy_match('Super Mario Wrld', candidates, threshold=0.7)
        assert result == 'SMW'

    def test_below_threshold_returns_none(self):
        candidates = {'completely different game': 'CDG'}
        assert fuzzy_match('Super Mario World', candidates, threshold=0.8) is None

    def test_empty_query_returns_none(self):
        assert fuzzy_match('', {'a': 'b'}) is None

    def test_empty_candidates_returns_none(self):
        assert fuzzy_match('query', {}) is None

    def test_short_query_returns_none(self):
        """Queries under 3 chars after normalization are rejected."""
        assert fuzzy_match('AB', {'ab': 'x'}) is None

    def test_picks_best_match(self):
        candidates = {
            'super mario world': 'SMW',
            'super mario bros': 'SMB',
            'donkey kong country': 'DKC',
        }
        assert fuzzy_match('Super Mario World', candidates) == 'SMW'
