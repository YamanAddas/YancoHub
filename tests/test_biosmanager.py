"""Tests for biosmanager.py — BIOS file scanning and status reporting."""

from pathlib import Path
from biosmanager import BIOSManager, KNOWN_BIOS, FILENAME_ALIASES


class TestBIOSManagerInit:
    def test_empty_on_init(self, bios_manager):
        assert bios_manager.found == {}
        assert bios_manager.bios_dirs == []

    def test_bundled_dir_set(self, bios_manager):
        assert bios_manager._bundled_dir.name == 'bios'


class TestBIOSScan:
    def test_finds_known_bios_file(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'bios'
        bios_dir.mkdir()
        # Create a fake GBA BIOS file
        (bios_dir / 'gba_bios.bin').write_bytes(b'\x00' * 16384)
        bios_manager.set_bios_dirs([str(bios_dir)])
        assert 'gba' in bios_manager.found
        assert 'gba_bios.bin' in bios_manager.found['gba']

    def test_finds_bios_in_subfolder(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'bios'
        sub = bios_dir / 'psx'
        sub.mkdir(parents=True)
        (sub / 'scph5501.bin').write_bytes(b'\x00' * 512)
        bios_manager.set_bios_dirs([str(bios_dir)])
        assert 'psx' in bios_manager.found

    def test_case_insensitive_matching(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'bios'
        bios_dir.mkdir()
        (bios_dir / 'GBA_BIOS.BIN').write_bytes(b'\x00' * 16384)
        bios_manager.set_bios_dirs([str(bios_dir)])
        assert 'gba' in bios_manager.found

    def test_alias_matching(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'bios'
        bios_dir.mkdir()
        (bios_dir / 'gba.bin').write_bytes(b'\x00' * 16384)
        bios_manager.set_bios_dirs([str(bios_dir)])
        assert 'gba' in bios_manager.found

    def test_ignores_nonexistent_dirs(self, bios_manager, tmp_path):
        bios_manager.set_bios_dirs([str(tmp_path / 'does_not_exist')])
        assert bios_manager.found == {} or len(bios_manager.found) == 0

    def test_empty_dir_scan(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'empty_bios'
        bios_dir.mkdir()
        bios_manager.set_bios_dirs([str(bios_dir)])
        # Only bundled dir may have results


class TestBIOSStatus:
    def test_status_covers_all_known_systems(self, bios_manager):
        status = bios_manager.get_status()
        for system_id in KNOWN_BIOS:
            assert system_id in status
            assert 'ready' in status[system_id]
            assert 'files' in status[system_id]

    def test_status_shows_not_ready_without_required(self, bios_manager):
        """Systems with required BIOS files should be not-ready if files are missing."""
        status = bios_manager.get_status()
        # NDS requires bios7/bios9 — should not be ready without them
        if not any(f['found'] for f in status['nds']['files'] if f['required']):
            assert status['nds']['ready'] is False

    def test_bundled_systems_can_be_ready(self, bios_manager):
        """GBA/PSX have bundled BIOS — ready even without user files."""
        status = bios_manager.get_status()
        # GBA has bundled=True, required=False — should be ready
        assert status['gba']['ready'] is True


class TestGetBiosPath:
    def test_returns_found_path(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'bios'
        bios_dir.mkdir()
        gba_file = bios_dir / 'gba_bios.bin'
        gba_file.write_bytes(b'\x00' * 16384)
        bios_manager.set_bios_dirs([str(bios_dir)])
        path = bios_manager.get_bios_path('gba', 'gba_bios.bin')
        assert path is not None
        assert 'gba_bios.bin' in path

    def test_returns_none_for_missing_system(self, bios_manager):
        assert bios_manager.get_bios_path('unknown_system') is None

    def test_returns_first_found_without_filename(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'bios'
        bios_dir.mkdir()
        (bios_dir / 'scph5501.bin').write_bytes(b'\x00' * 512)
        bios_manager.set_bios_dirs([str(bios_dir)])
        path = bios_manager.get_bios_path('psx')
        assert path is not None


class TestGetBiosDirs:
    def test_returns_configured_dirs(self, bios_manager, tmp_path):
        bios_dir = tmp_path / 'bios'
        bios_dir.mkdir()
        bios_manager.set_bios_dirs([str(bios_dir)])
        dirs = bios_manager.get_bios_dirs()
        assert str(bios_dir) in dirs


class TestKnownBIOSIntegrity:
    def test_all_entries_have_required_fields(self):
        for system_id, info in KNOWN_BIOS.items():
            assert 'name' in info, f"Missing 'name' in {system_id}"
            assert 'files' in info, f"Missing 'files' in {system_id}"
            for bios_file in info['files']:
                assert 'name' in bios_file, f"Missing file 'name' in {system_id}"

    def test_aliases_reference_valid_systems(self):
        for alias, (sys_id, target) in FILENAME_ALIASES.items():
            assert sys_id in KNOWN_BIOS, f"Alias '{alias}' references unknown system '{sys_id}'"
