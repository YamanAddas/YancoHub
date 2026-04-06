"""Tests for metadata.py — MetadataDB (SQLite cache) and MetadataFetcher."""

import time
from unittest.mock import patch, MagicMock


class TestMetadataDB:
    def test_put_and_get(self, metadata_db):
        metadata_db.put('steam_100', title='Half-Life', genre='FPS')
        result = metadata_db.get('steam_100')
        assert result is not None
        assert result['title'] == 'Half-Life'
        assert result['genre'] == 'FPS'
        assert result['cached_at'] is not None

    def test_get_nonexistent(self, metadata_db):
        assert metadata_db.get('nonexistent') is None

    def test_upsert_updates_existing(self, metadata_db):
        metadata_db.put('steam_100', title='Half-Life', genre='FPS')
        metadata_db.put('steam_100', title='Half-Life', genre='FPS, Action')
        result = metadata_db.get('steam_100')
        assert result['genre'] == 'FPS, Action'

    def test_partial_update_preserves_fields(self, metadata_db):
        metadata_db.put('steam_100', title='Half-Life', genre='FPS', developer='Valve')
        metadata_db.put('steam_100', description='A classic FPS')
        result = metadata_db.get('steam_100')
        assert result['description'] == 'A classic FPS'
        # Previous fields should be preserved via upsert
        assert result['title'] == 'Half-Life'

    def test_multiple_games(self, metadata_db):
        metadata_db.put('steam_100', title='Half-Life')
        metadata_db.put('steam_200', title='Portal')
        assert metadata_db.get('steam_100')['title'] == 'Half-Life'
        assert metadata_db.get('steam_200')['title'] == 'Portal'

    def test_null_fields(self, metadata_db):
        metadata_db.put('steam_100', title='Test Game')
        result = metadata_db.get('steam_100')
        assert result['developer'] is None
        assert result['rating'] is None


class TestMetadataFetcherSteam:
    @patch('metadata.requests.Session')
    def test_fetch_steam_metadata(self, mock_session_cls, tmp_path):
        from metadata import MetadataFetcher, MetadataDB

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            '100': {
                'success': True,
                'data': {
                    'name': 'Half-Life',
                    'short_description': 'A groundbreaking FPS',
                    'genres': [{'description': 'Action'}, {'description': 'FPS'}],
                    'developers': ['Valve'],
                    'publishers': ['Valve'],
                    'release_date': {'date': 'Nov 19, 1998'},
                    'metacritic': {'score': 96},
                    'recommendations': {'total': 100000},
                },
            }
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        fetcher = MetadataFetcher()
        fetcher.db = MetadataDB(db_path=tmp_path / 'test.db')
        fetcher._session = mock_session

        result = fetcher.get_metadata('steam_100', 'Half-Life', source='steam')
        assert result is not None
        assert result['title'] == 'Half-Life'
        assert 'Action' in result['genre']
        assert result['release_year'] == 1998
        assert result['developer'] == 'Valve'

    @patch('metadata.requests.Session')
    def test_steam_api_failure_falls_back(self, mock_session_cls, tmp_path):
        from metadata import MetadataFetcher, MetadataDB

        mock_session = MagicMock()
        # Steam fails
        steam_resp = MagicMock()
        steam_resp.status_code = 500
        # Wikipedia also fails
        wiki_resp = MagicMock()
        wiki_resp.status_code = 404

        mock_session.get.side_effect = [steam_resp, wiki_resp, wiki_resp]
        mock_session_cls.return_value = mock_session

        fetcher = MetadataFetcher()
        fetcher.db = MetadataDB(db_path=tmp_path / 'test.db')
        fetcher._session = mock_session

        result = fetcher.get_metadata('steam_999', 'Unknown Game', source='steam')
        # Should still return something (minimal entry)
        assert result is not None
        assert result['title'] == 'Unknown Game'


class TestMetadataFetcherWikipedia:
    @patch('metadata.requests.Session')
    def test_fetch_wikipedia_summary(self, mock_session_cls, tmp_path):
        from metadata import MetadataFetcher, MetadataDB

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'extract': 'Hades is a roguelike action dungeon crawler video game developed and published by Supergiant Games. It was released for macOS, Nintendo Switch, and Windows in September 2020.',
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        fetcher = MetadataFetcher()
        fetcher.db = MetadataDB(db_path=tmp_path / 'test.db')
        fetcher._session = mock_session

        result = fetcher.get_metadata('epic_hades', 'Hades', source='epic')
        assert result is not None
        assert 'roguelike' in result.get('description', '').lower()

    @patch('metadata.requests.Session')
    def test_short_extract_rejected(self, mock_session_cls, tmp_path):
        from metadata import MetadataFetcher, MetadataDB

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'extract': 'Too short.'}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        fetcher = MetadataFetcher()
        fetcher.db = MetadataDB(db_path=tmp_path / 'test.db')
        fetcher._session = mock_session

        result = fetcher.get_metadata('gog_test', 'TestGame', source='gog')
        # Should store minimal entry since wiki extract was too short
        assert result is not None
        assert result['title'] == 'TestGame'


class TestEnrichGames:
    @patch('metadata.requests.Session')
    def test_enriches_uncached_games(self, mock_session_cls, tmp_path):
        from metadata import MetadataFetcher, MetadataDB

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'extract': 'A great action adventure game with amazing gameplay and story elements that make it worth playing.',
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        fetcher = MetadataFetcher()
        fetcher.db = MetadataDB(db_path=tmp_path / 'test.db')
        fetcher._session = mock_session

        games = [
            {'id': 'gog_1', 'name': 'Game One', 'source': 'gog'},
            {'id': 'gog_2', 'name': 'Game Two', 'source': 'gog'},
        ]
        fetcher.enrich_games(games, batch_delay=0)
        assert fetcher.db.get('gog_1') is not None
        assert fetcher.db.get('gog_2') is not None

    @patch('metadata.requests.Session')
    def test_skips_already_cached(self, mock_session_cls, tmp_path):
        from metadata import MetadataFetcher, MetadataDB

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        fetcher = MetadataFetcher()
        fetcher.db = MetadataDB(db_path=tmp_path / 'test.db')
        fetcher._session = mock_session

        # Pre-cache
        fetcher.db.put('gog_1', title='Cached Game', description='Already here')

        games = [{'id': 'gog_1', 'name': 'Cached Game', 'source': 'gog'}]
        fetcher.enrich_games(games, batch_delay=0)
        # Should not have made any HTTP calls
        mock_session.get.assert_not_called()
