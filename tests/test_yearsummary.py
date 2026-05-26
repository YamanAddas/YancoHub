"""Tests for yearsummary.compute_year_summary — pure-data, no app imports."""

from datetime import datetime, timezone

import yearsummary as ys


def _ts(year, month, day=1):
    return datetime(year, month, day, tzinfo=timezone.utc).timestamp()


def _library():
    return [
        {'id': 'steam_1', 'name': 'Hades', 'source': 'steam', 'system': 'steam'},
        {'id': 'steam_2', 'name': 'Slay the Spire', 'source': 'steam', 'system': 'steam'},
        {'id': 'epic_1', 'name': 'Fortnite', 'source': 'epic', 'system': 'epic'},
        {'id': 'rom_snes_1', 'name': 'Chrono Trigger', 'source': 'rom', 'system': 'snes'},
        {'id': 'orphan', 'name': 'No-Sessions Game', 'source': 'steam', 'system': 'steam'},
    ]


def _playtime():
    return {
        'steam_1': {'total_hours': 12.5, 'last_played': _ts(2026, 3, 15), 'session_count': 8},
        'steam_2': {'total_hours': 8.0,  'last_played': _ts(2026, 5, 2),  'session_count': 4},
        'epic_1':  {'total_hours': 4.0,  'last_played': _ts(2026, 11, 20), 'session_count': 2},
        'rom_snes_1': {'total_hours': 20.0, 'last_played': _ts(2024, 8, 1), 'session_count': 5},
        'zero_game': {'total_hours': 0,   'last_played': _ts(2026, 1, 1), 'session_count': 0},
    }


class _FakeMetadataDB:
    """Minimal duck-typed metadata DB for tests."""

    def __init__(self, data):
        self._data = data

    def get(self, game_id):
        return self._data.get(game_id)


def test_filters_to_games_touched_in_year():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    names = [g['name'] for g in summary['top_games']]
    assert 'Hades' in names
    assert 'Slay the Spire' in names
    assert 'Fortnite' in names
    # Played in 2024, excluded
    assert 'Chrono Trigger' not in names
    # No matching library entry
    assert 'No-Sessions Game' not in names
    assert summary['games_touched'] == 3


def test_top_games_sorted_by_hours_desc():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    hours = [g['hours'] for g in summary['top_games']]
    assert hours == sorted(hours, reverse=True)
    assert summary['top_games'][0]['name'] == 'Hades'


def test_hours_total_sums_touched_games():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    # 12.5 + 8.0 + 4.0 = 24.5
    assert summary['hours_total'] == 24.5


def test_by_system_counts_and_hours():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    steam = next(b for b in summary['by_system'] if b['system'] == 'steam')
    epic = next(b for b in summary['by_system'] if b['system'] == 'epic')
    assert steam['count'] == 2
    assert steam['hours'] == 20.5  # 12.5 + 8.0
    assert epic['count'] == 1
    assert epic['hours'] == 4.0


def test_by_month_buckets_and_top_game():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    by_m = {b['month']: b for b in summary['by_month']}
    assert len(summary['by_month']) == 12
    assert by_m[3]['hours'] == 12.5
    assert by_m[3]['top_game'] == 'Hades'
    assert by_m[5]['hours'] == 8.0
    assert by_m[11]['hours'] == 4.0
    assert by_m[1]['hours'] == 0
    assert by_m[1]['top_game'] is None
    assert by_m[3]['label'] == 'Mar'


def test_by_genre_uses_metadata_db():
    db = _FakeMetadataDB({
        'steam_1': {'genre': 'Roguelike, Action'},
        'steam_2': {'genre': 'Deck-builder'},
        'epic_1': {'genre': 'Shooter'},
    })
    summary = ys.compute_year_summary(2026, _playtime(), _library(), db)
    assert summary['by_genre'][0] == {'genre': 'Roguelike', 'hours': 12.5}
    genres = {g['genre'] for g in summary['by_genre']}
    assert genres == {'Roguelike', 'Deck-builder', 'Shooter'}


def test_by_genre_skips_when_no_metadata():
    summary = ys.compute_year_summary(2026, _playtime(), _library(), metadata_db=None)
    assert summary['by_genre'] == []


def test_first_and_last_play():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    assert summary['first_play']['name'] == 'Hades'
    assert summary['last_play']['name'] == 'Fortnite'


def test_all_time_independent_of_year():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    # All sessions with hours>0: Hades 12.5 + StS 8 + Fortnite 4 + Chrono 20 = 44.5
    assert summary['all_time']['hours'] == 44.5
    assert summary['all_time']['games'] == 4


def test_empty_year_returns_zero_state():
    summary = ys.compute_year_summary(2030, _playtime(), _library())
    assert summary['games_touched'] == 0
    assert summary['hours_total'] == 0
    assert summary['top_games'] == []
    assert summary['first_play'] is None
    assert summary['last_play'] is None
    assert len(summary['by_month']) == 12
    assert all(b['hours'] == 0 for b in summary['by_month'])


def test_artwork_urls_match_game_ids():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    for g in summary['top_games']:
        assert g['artwork_url'] == f"/api/artwork/{g['game_id']}/cover"


def test_iso_date_formatting():
    summary = ys.compute_year_summary(2026, _playtime(), _library())
    hades = next(g for g in summary['top_games'] if g['name'] == 'Hades')
    assert hades['last_played_iso'] == '2026-03-15'
