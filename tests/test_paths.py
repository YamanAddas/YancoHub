"""Tests for paths.py — portable detection, APPDATA paths, migration."""

import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def app_dir(tmp_path):
    """Simulate the app directory with paths module."""
    return tmp_path


@pytest.fixture
def paths_module(app_dir, monkeypatch):
    """Import paths with a mocked APP_DIR."""
    monkeypatch.setenv('APPDATA', str(app_dir / 'roaming'))
    monkeypatch.setenv('LOCALAPPDATA', str(app_dir / 'local'))

    import paths
    monkeypatch.setattr(paths, 'APP_DIR', app_dir)
    return paths


class TestPortableDetection:
    def test_not_portable_by_default(self, paths_module):
        assert paths_module.is_portable() is False

    def test_portable_when_marker_exists(self, paths_module, app_dir):
        (app_dir / 'portable.txt').write_text('portable mode')
        assert paths_module.is_portable() is True


class TestDataDir:
    def test_normal_mode_uses_appdata(self, paths_module, app_dir):
        result = paths_module.get_data_dir()
        assert 'roaming' in str(result).lower() or 'YancoHub' in str(result)
        assert result.exists()

    def test_portable_mode_uses_app_dir(self, paths_module, app_dir):
        (app_dir / 'portable.txt').write_text('portable')
        result = paths_module.get_data_dir()
        assert result == app_dir


class TestCacheDir:
    def test_normal_mode_uses_localappdata(self, paths_module, app_dir):
        result = paths_module.get_cache_dir()
        assert 'cache' in str(result).lower()
        assert result.exists()

    def test_portable_mode_uses_app_dir_cache(self, paths_module, app_dir):
        (app_dir / 'portable.txt').write_text('portable')
        result = paths_module.get_cache_dir()
        assert result == app_dir / 'cache'
        assert result.exists()


class TestLogDir:
    def test_normal_mode_uses_localappdata(self, paths_module, app_dir):
        result = paths_module.get_log_dir()
        assert 'logs' in str(result).lower()
        assert result.exists()

    def test_portable_mode_uses_app_dir_logs(self, paths_module, app_dir):
        (app_dir / 'portable.txt').write_text('portable')
        result = paths_module.get_log_dir()
        assert result == app_dir / 'logs'
        assert result.exists()


class TestMigration:
    def test_migrates_userdata(self, paths_module, app_dir):
        # Create old file
        old = app_dir / 'userdata.json'
        old.write_text('{"test": true}')
        paths_module.migrate_legacy_data()
        # New location should exist
        new = paths_module.get_data_dir() / 'userdata.json'
        assert new.exists()
        assert new.read_text() == '{"test": true}'
        # Old renamed
        assert not old.exists()
        assert (app_dir / 'userdata.json.migrated').exists()

    def test_skips_if_target_exists(self, paths_module, app_dir):
        old = app_dir / 'userdata.json'
        old.write_text('old')
        new_dir = paths_module.get_data_dir()
        new = new_dir / 'userdata.json'
        new.write_text('new')
        paths_module.migrate_legacy_data()
        # Old not renamed, new not overwritten
        assert old.exists()
        assert new.read_text() == 'new'

    def test_skips_in_portable_mode(self, paths_module, app_dir):
        (app_dir / 'portable.txt').write_text('portable')
        old = app_dir / 'userdata.json'
        old.write_text('{"test": true}')
        paths_module.migrate_legacy_data()
        # Nothing should change
        assert old.exists()

    def test_migrates_metadata_db(self, paths_module, app_dir):
        cache = app_dir / 'cache'
        cache.mkdir()
        old_db = cache / 'metadata.db'
        old_db.write_text('SQLITE')
        paths_module.migrate_legacy_data()
        new_db = paths_module.get_cache_dir() / 'metadata.db'
        assert new_db.exists()
        # Original DB is NOT renamed (cache is expendable)
        assert old_db.exists()
