"""Tests for app.py — Flask API routes via test client.

Imports the real app module (dependencies now installed) and replaces
the module-level singletons with mocks to avoid real filesystem/network access.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the real app — deps must be installed
import app as app_module


@pytest.fixture
def client():
    """Flask test client with mocked backend services."""
    app_module.app.config['TESTING'] = True

    # Save originals
    orig_ud = app_module.userdata
    orig_scanner = app_module.scanner
    orig_fetcher = app_module.metadata_fetcher
    orig_artwork = app_module.artwork_scraper
    orig_bios = app_module.bios_manager
    orig_catbyte = app_module.catbyte
    orig_chat = app_module.chat_history
    orig_lib = app_module.game_library
    orig_idx = app_module.game_index
    orig_scan = app_module.scan_complete

    # Install mocks
    mock_ud = MagicMock()
    mock_ud.get_settings.return_value = {}
    mock_ud.get_catbyte_config.return_value = {}
    mock_ud.get_rom_dirs.return_value = []
    mock_ud.get_local_dirs.return_value = []
    mock_ud.get_favorites.return_value = []
    mock_ud.get_hidden_systems.return_value = []
    mock_ud.get_playtime.return_value = {}
    mock_ud.get_collections.return_value = {}
    app_module.userdata = mock_ud

    mock_fetcher = MagicMock()
    mock_fetcher.db = MagicMock()
    mock_fetcher.db.get.return_value = None
    app_module.metadata_fetcher = mock_fetcher

    mock_artwork = MagicMock()
    mock_artwork.batch_progress = {'active': False}
    app_module.artwork_scraper = mock_artwork

    app_module.game_library = []
    app_module.game_index = {}
    app_module.scan_complete = True

    with app_module.app.test_client() as c:
        # Attach mocks to client for test access
        c._mock_ud = mock_ud
        c._mock_fetcher = mock_fetcher
        c._mock_artwork = mock_artwork
        yield c

    # Restore originals
    app_module.userdata = orig_ud
    app_module.scanner = orig_scanner
    app_module.metadata_fetcher = orig_fetcher
    app_module.artwork_scraper = orig_artwork
    app_module.bios_manager = orig_bios
    app_module.catbyte = orig_catbyte
    app_module.chat_history = orig_chat
    app_module.game_library = orig_lib
    app_module.game_index = orig_idx
    app_module.scan_complete = orig_scan


VALID_ORIGIN = f'http://127.0.0.1:8745'


# ── Health & Index ─────────────────────────────────────────────────────────

class TestHealthAndIndex:
    def test_health_endpoint(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert 'games' in data

    def test_index_returns_html(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'html' in resp.data.lower()


# ── Games API ──────────────────────────────────────────────────────────────

class TestGamesAPI:
    def test_games_returns_list(self, client):
        app_module.game_library = [
            {'id': 'steam_100', 'name': 'Half-Life', 'source': 'steam'},
        ]
        app_module.game_index = {'steam_100': app_module.game_library[0]}
        resp = client.get('/api/games')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['name'] == 'Half-Life'

    def test_games_filter_by_source(self, client):
        app_module.game_library = [
            {'id': 'steam_100', 'name': 'Half-Life', 'source': 'steam'},
            {'id': 'epic_200', 'name': 'Fortnite', 'source': 'epic'},
        ]
        resp = client.get('/api/games?source=steam')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['source'] == 'steam'

    def test_games_filter_by_system(self, client):
        app_module.game_library = [
            {'id': 'rom_snes_1', 'name': 'Mario', 'source': 'rom', 'system': 'snes'},
            {'id': 'rom_gba_1', 'name': 'Metroid', 'source': 'rom', 'system': 'gba'},
        ]
        resp = client.get('/api/games?system=snes')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Mario'

    def test_games_scanning_state(self, client):
        app_module.scan_complete = False
        resp = client.get('/api/games')
        data = resp.get_json()
        assert data['status'] == 'scanning'

    def test_games_hides_hidden_systems(self, client):
        client._mock_ud.get_hidden_systems.return_value = ['atari2600']
        app_module.game_library = [
            {'id': 'rom_atari_1', 'name': 'Pitfall', 'source': 'rom', 'system': 'atari2600'},
            {'id': 'steam_100', 'name': 'Half-Life', 'source': 'steam'},
        ]
        resp = client.get('/api/games')
        data = resp.get_json()
        names = [g['name'] for g in data]
        assert 'Pitfall' not in names
        assert 'Half-Life' in names

    def test_games_enriched_with_playtime(self, client):
        client._mock_ud.get_playtime.return_value = {
            'steam_100': {'total_hours': 5.2, 'last_played': 1234567890, 'session_count': 3}
        }
        client._mock_ud.get_favorites.return_value = ['steam_100']
        app_module.game_library = [
            {'id': 'steam_100', 'name': 'Half-Life', 'source': 'steam'},
        ]
        app_module.game_index = {'steam_100': app_module.game_library[0]}
        resp = client.get('/api/games')
        data = resp.get_json()
        assert data[0]['playtime_hours'] == 5.2
        assert data[0]['is_favorite'] is True


# ── Search API ─────────────────────────────────────────────────────────────

class TestSearchAPI:
    def test_search_empty_query(self, client):
        resp = client.get('/api/search?q=')
        assert resp.get_json() == []

    def test_search_finds_games(self, client):
        app_module.game_library = [
            {'id': 'steam_100', 'name': 'Half-Life', 'source': 'steam'},
            {'id': 'steam_200', 'name': 'Portal', 'source': 'steam'},
        ]
        resp = client.get('/api/search?q=half')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Half-Life'

    def test_search_case_insensitive(self, client):
        app_module.game_library = [
            {'id': 'steam_100', 'name': 'Half-Life', 'source': 'steam'},
        ]
        resp = client.get('/api/search?q=HALF')
        assert len(resp.get_json()) == 1

    def test_search_limits_results(self, client):
        app_module.game_library = [
            {'id': f'steam_{i}', 'name': f'Game {i}', 'source': 'steam'}
            for i in range(100)
        ]
        resp = client.get('/api/search?q=game')
        assert len(resp.get_json()) <= 50

    def test_search_sorts_prefix_matches_first(self, client):
        app_module.game_library = [
            {'id': 'steam_1', 'name': 'The Half-Life Story', 'source': 'steam'},
            {'id': 'steam_2', 'name': 'Half-Life', 'source': 'steam'},
        ]
        resp = client.get('/api/search?q=half')
        data = resp.get_json()
        assert data[0]['name'] == 'Half-Life'


# ── Collections API ────────────────────────────────────────────────────────

class TestCollectionsAPI:
    def test_get_collections(self, client):
        client._mock_ud.get_collections.return_value = {'RPGs': ['steam_1']}
        resp = client.get('/api/collections')
        assert resp.status_code == 200

    def test_create_collection(self, client):
        client._mock_ud.create_collection.return_value = True
        resp = client.post('/api/collections',
                           json={'name': 'RPGs'},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'created'

    def test_create_collection_empty_name(self, client):
        resp = client.post('/api/collections',
                           json={'name': ''},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 400

    def test_create_collection_whitespace_name(self, client):
        resp = client.post('/api/collections',
                           json={'name': '   '},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 400

    def test_create_duplicate_collection(self, client):
        client._mock_ud.create_collection.return_value = False
        resp = client.post('/api/collections',
                           json={'name': 'RPGs'},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 409

    def test_delete_collection(self, client):
        client._mock_ud.delete_collection.return_value = True
        resp = client.delete('/api/collections/RPGs',
                             headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 200

    def test_delete_nonexistent_collection(self, client):
        client._mock_ud.delete_collection.return_value = False
        resp = client.delete('/api/collections/nope',
                             headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 404

    def test_add_game_to_collection(self, client):
        client._mock_ud.add_to_collection.return_value = True
        resp = client.post('/api/collections/RPGs/games',
                           json={'game_id': 'steam_100'},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 200

    def test_remove_game_from_collection(self, client):
        client._mock_ud.remove_from_collection.return_value = True
        resp = client.delete('/api/collections/RPGs/games/steam_100',
                             headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 200


# ── Favorites API ──────────────────────────────────────────────────────────

class TestFavoritesAPI:
    def test_get_favorites(self, client):
        client._mock_ud.get_favorites.return_value = ['steam_100']
        resp = client.get('/api/favorites')
        assert resp.status_code == 200

    def test_toggle_favorite(self, client):
        client._mock_ud.toggle_favorite.return_value = True
        resp = client.post('/api/favorites/toggle',
                           json={'game_id': 'steam_100'},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['is_favorite'] is True
        assert data['game_id'] == 'steam_100'


# ── Hidden Systems API ─────────────────────────────────────────────────────

class TestHiddenSystemsAPI:
    def test_get_hidden_systems(self, client):
        client._mock_ud.get_hidden_systems.return_value = ['atari2600']
        resp = client.get('/api/hidden-systems')
        assert resp.status_code == 200

    def test_toggle_hidden_system(self, client):
        client._mock_ud.toggle_hidden_system.return_value = True
        resp = client.post('/api/hidden-systems/toggle',
                           json={'system': 'atari2600'},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['is_hidden'] is True


# ── Playtime API ───────────────────────────────────────────────────────────

class TestPlaytimeAPI:
    def test_get_playtime(self, client):
        client._mock_ud.get_playtime.return_value = {
            'steam_100': {'total_hours': 5.2, 'last_played': 1234567890}
        }
        resp = client.get('/api/playtime')
        assert resp.status_code == 200


# ── CSRF Protection ───────────────────────────────────────────────────────

class TestCSRFProtection:
    def test_post_without_origin_allowed(self, client):
        client._mock_ud.toggle_favorite.return_value = True
        resp = client.post('/api/favorites/toggle',
                           json={'game_id': 'steam_100'})
        assert resp.status_code == 200

    def test_post_with_valid_origin(self, client):
        client._mock_ud.toggle_favorite.return_value = True
        resp = client.post('/api/favorites/toggle',
                           json={'game_id': 'steam_100'},
                           headers={'Origin': VALID_ORIGIN})
        assert resp.status_code == 200

    def test_post_with_invalid_origin_blocked(self, client):
        resp = client.post('/api/favorites/toggle',
                           json={'game_id': 'steam_100'},
                           headers={'Origin': 'http://evil.com'})
        assert resp.status_code == 403

    def test_get_ignores_origin(self, client):
        resp = client.get('/health',
                          headers={'Origin': 'http://evil.com'})
        assert resp.status_code == 200

    def test_referer_based_origin_check(self, client):
        resp = client.post('/api/favorites/toggle',
                           json={'game_id': 'steam_100'},
                           headers={'Referer': 'http://evil.com/page'})
        assert resp.status_code == 403


# ── Artwork API ────────────────────────────────────────────────────────────

class TestArtworkAPI:
    def test_invalid_art_type(self, client):
        app_module.game_library = [{'id': 'steam_100', 'name': 'Test', 'source': 'steam'}]
        app_module.game_index = {'steam_100': app_module.game_library[0]}
        resp = client.get('/api/artwork/steam_100/invalid_type')
        assert resp.status_code == 400

    def test_missing_game_404(self, client):
        resp = client.get('/api/artwork/nonexistent/cover')
        assert resp.status_code == 404


class TestGamepadAPI:
    def test_get_settings_includes_defaults(self, client):
        resp = client.get('/api/settings')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'values' in data and 'schema' in data
        assert data['values']['gamepad_mapping'] == {}
        assert data['values']['show_uninstalled'] is True

    def test_set_mapping_persists_cleaned(self, client):
        mapping = {'a': 1, 'b': 0, 'start': 9}
        resp = client.patch('/api/settings', json={'gamepad_mapping': mapping})
        assert resp.status_code == 200
        assert resp.get_json()['errors'] == {}
        client._mock_ud.update_settings.assert_called()
        saved = client._mock_ud.update_settings.call_args[0][0]
        assert saved['gamepad_mapping'] == {'a': 1, 'b': 0, 'start': 9}

    def test_set_mapping_rejects_non_dict(self, client):
        resp = client.patch('/api/settings', json={'gamepad_mapping': 'bad'})
        assert resp.status_code == 200
        assert 'gamepad_mapping' in resp.get_json()['errors']

    def test_set_mapping_filters_invalid_values(self, client):
        mapping = {'a': 2, 'bad_key': -1, 'b': 'string'}
        resp = client.patch('/api/settings', json={'gamepad_mapping': mapping})
        assert resp.status_code == 200
        saved = client._mock_ud.update_settings.call_args[0][0]
        assert saved['gamepad_mapping'] == {'a': 2}

    def test_unknown_setting_reports_error(self, client):
        resp = client.patch('/api/settings', json={'nope': True})
        assert resp.status_code == 200
        assert 'nope' in resp.get_json()['errors']

    def test_gamepad_status_endpoint(self, client):
        resp = client.get('/api/gamepad/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'xinput_available' in data
        assert 'detected' in data
