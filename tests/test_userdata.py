"""Tests for userdata.py — UserData persistence, sessions, collections, favorites."""

import json
import time
from pathlib import Path


class TestUserDataInit:
    def test_creates_with_defaults(self, userdata_instance):
        assert 'sessions' in userdata_instance.data
        assert 'favorites' in userdata_instance.data
        assert 'collections' in userdata_instance.data
        assert 'settings' in userdata_instance.data

    def test_loads_existing_file(self, tmp_path):
        from userdata import UserData
        data_file = tmp_path / 'existing.json'
        data_file.write_text(json.dumps({
            'sessions': {},
            'favorites': ['steam_123'],
            'collections': {'RPGs': ['steam_456']},
            'hidden_systems': [],
            'local_dirs': [],
            'rom_dirs': [],
            'accounts': {},
            'settings': {},
        }))
        ud = UserData(data_file=data_file)
        assert ud.get_favorites() == ['steam_123']
        assert 'RPGs' in ud.get_collections()
        ud.flush()

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path):
        from userdata import UserData
        data_file = tmp_path / 'corrupt.json'
        data_file.write_text('NOT VALID JSON {{{')
        ud = UserData(data_file=data_file)
        assert ud.data['favorites'] == []
        ud.flush()

    def test_merges_new_defaults(self, tmp_path):
        """Existing files missing new keys get them from DEFAULT_DATA."""
        from userdata import UserData
        data_file = tmp_path / 'old.json'
        data_file.write_text(json.dumps({'sessions': {}, 'favorites': ['x']}))
        ud = UserData(data_file=data_file)
        assert 'collections' in ud.data
        assert ud.get_favorites() == ['x']
        ud.flush()


class TestPlaySessions:
    def test_session_start_creates_entry(self, userdata_instance):
        userdata_instance.session_start('steam_100')
        pt = userdata_instance.get_playtime('steam_100')
        assert pt['session_count'] == 1
        assert pt['last_played'] is not None

    def test_session_end_records_time(self, userdata_instance):
        userdata_instance.session_start('steam_100')
        time.sleep(0.05)
        userdata_instance.session_end('steam_100')
        pt = userdata_instance.get_playtime('steam_100')
        assert pt['total_hours'] >= 0
        assert pt['session_count'] == 1

    def test_multiple_sessions_accumulate(self, userdata_instance):
        userdata_instance.session_start('steam_100')
        userdata_instance.session_end('steam_100')
        userdata_instance.session_start('steam_100')
        userdata_instance.session_end('steam_100')
        pt = userdata_instance.get_playtime('steam_100')
        assert pt['session_count'] == 2

    def test_starting_new_game_ends_previous(self, userdata_instance):
        userdata_instance.session_start('game_a')
        userdata_instance.session_start('game_b')
        # game_a should be ended
        session_a = userdata_instance.data['sessions']['game_a']
        assert session_a['active_since'] is None

    def test_get_playtime_all(self, userdata_instance):
        userdata_instance.session_start('game_a')
        userdata_instance.session_end('game_a')
        userdata_instance.session_start('game_b')
        userdata_instance.session_end('game_b')
        all_pt = userdata_instance.get_playtime()
        assert 'game_a' in all_pt
        assert 'game_b' in all_pt

    def test_get_last_played(self, userdata_instance):
        userdata_instance.session_start('game_a')
        userdata_instance.session_end('game_a')
        time.sleep(0.01)
        userdata_instance.session_start('game_b')
        userdata_instance.session_end('game_b')
        assert userdata_instance.get_last_played() == 'game_b'

    def test_get_last_played_empty(self, userdata_instance):
        assert userdata_instance.get_last_played() is None

    def test_session_end_nonexistent_is_noop(self, userdata_instance):
        userdata_instance.session_end('nonexistent')  # should not raise


class TestCollections:
    def test_create_collection(self, userdata_instance):
        assert userdata_instance.create_collection('RPGs') is True
        assert 'RPGs' in userdata_instance.get_collections()

    def test_create_duplicate_returns_false(self, userdata_instance):
        userdata_instance.create_collection('RPGs')
        assert userdata_instance.create_collection('RPGs') is False

    def test_delete_collection(self, userdata_instance):
        userdata_instance.create_collection('RPGs')
        assert userdata_instance.delete_collection('RPGs') is True
        assert 'RPGs' not in userdata_instance.get_collections()

    def test_delete_nonexistent_returns_false(self, userdata_instance):
        assert userdata_instance.delete_collection('nope') is False

    def test_add_game_to_collection(self, userdata_instance):
        userdata_instance.create_collection('RPGs')
        assert userdata_instance.add_to_collection('RPGs', 'steam_100') is True
        assert 'steam_100' in userdata_instance.get_collections()['RPGs']

    def test_add_duplicate_game_is_idempotent(self, userdata_instance):
        userdata_instance.create_collection('RPGs')
        userdata_instance.add_to_collection('RPGs', 'steam_100')
        userdata_instance.add_to_collection('RPGs', 'steam_100')
        assert userdata_instance.get_collections()['RPGs'].count('steam_100') == 1

    def test_add_to_nonexistent_collection(self, userdata_instance):
        assert userdata_instance.add_to_collection('nope', 'steam_100') is False

    def test_remove_from_collection(self, userdata_instance):
        userdata_instance.create_collection('RPGs')
        userdata_instance.add_to_collection('RPGs', 'steam_100')
        assert userdata_instance.remove_from_collection('RPGs', 'steam_100') is True
        assert 'steam_100' not in userdata_instance.get_collections()['RPGs']

    def test_remove_nonexistent_game(self, userdata_instance):
        userdata_instance.create_collection('RPGs')
        assert userdata_instance.remove_from_collection('RPGs', 'nope') is False


class TestFavorites:
    def test_toggle_adds_favorite(self, userdata_instance):
        result = userdata_instance.toggle_favorite('steam_100')
        assert result is True
        assert 'steam_100' in userdata_instance.get_favorites()

    def test_toggle_removes_favorite(self, userdata_instance):
        userdata_instance.toggle_favorite('steam_100')
        result = userdata_instance.toggle_favorite('steam_100')
        assert result is False
        assert 'steam_100' not in userdata_instance.get_favorites()

    def test_multiple_favorites(self, userdata_instance):
        userdata_instance.toggle_favorite('game_a')
        userdata_instance.toggle_favorite('game_b')
        favs = userdata_instance.get_favorites()
        assert 'game_a' in favs
        assert 'game_b' in favs


class TestHiddenSystems:
    def test_toggle_hides_system(self, userdata_instance):
        result = userdata_instance.toggle_hidden_system('atari2600')
        assert result is True
        assert 'atari2600' in userdata_instance.get_hidden_systems()

    def test_toggle_unhides_system(self, userdata_instance):
        userdata_instance.toggle_hidden_system('atari2600')
        result = userdata_instance.toggle_hidden_system('atari2600')
        assert result is False
        assert 'atari2600' not in userdata_instance.get_hidden_systems()


class TestDirectories:
    def test_add_local_dir(self, userdata_instance):
        result = userdata_instance.add_local_dir('C:\\Games')
        assert 'C:\\Games' in result

    def test_add_duplicate_local_dir(self, userdata_instance):
        userdata_instance.add_local_dir('C:\\Games')
        result = userdata_instance.add_local_dir('C:\\Games')
        assert result.count('C:\\Games') == 1

    def test_remove_local_dir(self, userdata_instance):
        userdata_instance.add_local_dir('C:\\Games')
        result = userdata_instance.remove_local_dir('C:\\Games')
        assert 'C:\\Games' not in result

    def test_add_rom_dir(self, userdata_instance):
        result = userdata_instance.add_rom_dir('C:\\ROMs')
        assert 'C:\\ROMs' in result

    def test_remove_rom_dir(self, userdata_instance):
        userdata_instance.add_rom_dir('C:\\ROMs')
        result = userdata_instance.remove_rom_dir('C:\\ROMs')
        assert 'C:\\ROMs' not in result


class TestAccounts:
    def test_set_steam_account(self, userdata_instance):
        userdata_instance.set_steam_account('key123', '76561198000', 'TestUser')
        acct = userdata_instance.get_steam_account()
        assert acct['api_key'] == 'key123'
        assert acct['steam_id'] == '76561198000'
        assert acct['persona_name'] == 'TestUser'
        assert acct['connected'] is True

    def test_disconnect_steam_account(self, userdata_instance):
        userdata_instance.set_steam_account('key123', '76561198000')
        userdata_instance.disconnect_steam_account()
        acct = userdata_instance.get_steam_account()
        assert acct['connected'] is False
        assert acct['api_key'] == ''

    def test_set_gog_galaxy_config(self, userdata_instance):
        userdata_instance.set_gog_galaxy_enabled(True, 'C:\\galaxy.db')
        config = userdata_instance.get_gog_galaxy_config()
        assert config['enabled'] is True
        assert config['db_path'] == 'C:\\galaxy.db'


class TestSettings:
    def test_get_default_settings(self, userdata_instance):
        settings = userdata_instance.get_settings()
        assert 'direct_launch' in settings

    def test_update_settings(self, userdata_instance):
        userdata_instance.update_settings({'direct_launch': False})
        assert userdata_instance.get_settings()['direct_launch'] is False


class TestDirectLaunchOverrides:
    def test_default_is_none(self, userdata_instance):
        assert userdata_instance.get_direct_launch_override('steam_100') is None

    def test_set_override(self, userdata_instance):
        userdata_instance.set_direct_launch_override('steam_100', True)
        assert userdata_instance.get_direct_launch_override('steam_100') is True

    def test_clear_override(self, userdata_instance):
        userdata_instance.set_direct_launch_override('steam_100', True)
        userdata_instance.set_direct_launch_override('steam_100', None)
        assert userdata_instance.get_direct_launch_override('steam_100') is None


class TestCatByteConfig:
    def test_get_default_config(self, userdata_instance):
        config = userdata_instance.get_catbyte_config()
        assert 'backend' in config

    def test_update_catbyte_config(self, userdata_instance):
        userdata_instance.update_catbyte_config({'backend': 'openai', 'model': 'gpt-4'})
        config = userdata_instance.get_catbyte_config()
        assert config['backend'] == 'openai'
        assert config['model'] == 'gpt-4'


class TestPersistence:
    def test_flush_writes_to_disk(self, tmp_path):
        from userdata import UserData
        data_file = tmp_path / 'persist.json'
        ud = UserData(data_file=data_file)
        ud.toggle_favorite('steam_100')
        ud.flush()
        # Read back from disk
        raw = json.loads(data_file.read_text())
        assert 'steam_100' in raw['favorites']
