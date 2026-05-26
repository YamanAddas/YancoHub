"""Tests for saveguardian.py — detection, backup, restore, retention."""

from pathlib import Path

import saveguardian as sg


# ── Detection ────────────────────────────────────────────────────────────────

def test_detect_exact_match(tmp_path):
    root = tmp_path / 'Documents'
    (root / 'Hades').mkdir(parents=True)
    (root / 'NotIt').mkdir()
    results = sg.detect_candidates('Hades', candidate_roots=[root])
    assert results, 'should find Hades'
    assert results[0]['path'].endswith('Hades')
    assert results[0]['score'] == 100


def test_detect_normalization(tmp_path):
    root = tmp_path / 'Documents'
    (root / 'My Games' / 'Slay The Spire').mkdir(parents=True)
    results = sg.detect_candidates('Slay the Spire', candidate_roots=[root / 'My Games'])
    assert any('Slay The Spire' in r['path'] for r in results)


def test_detect_substring_lower_score(tmp_path):
    root = tmp_path / 'Documents'
    (root / 'Hades II Saves').mkdir(parents=True)
    results = sg.detect_candidates('Hades', candidate_roots=[root])
    assert results
    assert results[0]['score'] in (60, 80)


def test_detect_empty_name():
    assert sg.detect_candidates('') == []


def test_detect_no_roots():
    assert sg.detect_candidates('AnyGame', candidate_roots=[]) == []


# ── Backup / list / restore ──────────────────────────────────────────────────

def _make_save(dir_: Path, payload: str = 'save-data-v1'):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / 'slot1.sav').write_text(payload, encoding='utf-8')
    (dir_ / 'config.ini').write_text('[mods]\nfoo=1', encoding='utf-8')


def test_backup_creates_zip_and_manifest(tmp_path):
    save_dir = tmp_path / 'game-saves'
    _make_save(save_dir)
    record = sg.backup(tmp_path / 'snaps', 'steam_1', [str(save_dir)], label='checkpoint')
    assert record is not None
    assert record['files'] == 2
    assert record['label'] == 'checkpoint'
    snaps = sg.list_backups(tmp_path / 'snaps', 'steam_1')
    assert len(snaps) == 1
    assert snaps[0]['id'] == record['id']


def test_backup_with_no_existing_paths_returns_none(tmp_path):
    assert sg.backup(tmp_path / 'snaps', 'gid', [str(tmp_path / 'does_not_exist')]) is None


def test_backup_skips_missing_paths_but_keeps_others(tmp_path):
    save_dir = tmp_path / 'real'
    _make_save(save_dir)
    record = sg.backup(tmp_path / 'snaps', 'gid', [
        str(save_dir),
        str(tmp_path / 'missing'),
    ])
    assert record is not None
    assert record['files'] == 2


def test_restore_round_trip(tmp_path):
    save_dir = tmp_path / 'game-saves'
    _make_save(save_dir, 'original payload')
    rec = sg.backup(tmp_path / 'snaps', 'gid', [str(save_dir)])
    # Corrupt the live saves
    (save_dir / 'slot1.sav').write_text('CORRUPTED', encoding='utf-8')
    (save_dir / 'extra.tmp').write_text('garbage', encoding='utf-8')
    result = sg.restore(tmp_path / 'snaps', 'gid', rec['id'])
    assert result['restored']['id'] == rec['id']
    assert (save_dir / 'slot1.sav').read_text(encoding='utf-8') == 'original payload'
    # Pre-restore snapshot of the corrupted state was taken
    assert result['pre_restore'] is not None
    assert result['pre_restore']['pre_restore'] is True


def test_restore_missing_backup_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        sg.restore(tmp_path / 'snaps', 'gid', '20990101T000000')


def test_delete_backup(tmp_path):
    save_dir = tmp_path / 'sv'
    _make_save(save_dir)
    rec = sg.backup(tmp_path / 'snaps', 'gid', [str(save_dir)])
    assert sg.delete_backup(tmp_path / 'snaps', 'gid', rec['id']) is True
    assert sg.list_backups(tmp_path / 'snaps', 'gid') == []
    assert sg.delete_backup(tmp_path / 'snaps', 'gid', 'does_not_exist') is False


def test_retention_evicts_oldest(tmp_path, monkeypatch):
    # Tighten the retention window for the test
    monkeypatch.setattr(sg, 'BACKUP_KEEP', 3)
    save_dir = tmp_path / 'sv'
    _make_save(save_dir)
    snaps_root = tmp_path / 'snaps'
    import time as _t
    ids = []
    for i in range(5):
        rec = sg.backup(snaps_root, 'gid', [str(save_dir)])
        ids.append(rec['id'])
        # zip names are timestamp-based to the second — bump to ensure distinct ids
        _t.sleep(1.05)
    kept = sg.list_backups(snaps_root, 'gid')
    assert len(kept) == 3
    kept_ids = {b['id'] for b in kept}
    # The 3 newest should remain
    assert kept_ids == set(ids[-3:])
    # And the evicted zip files are gone
    game_dir = snaps_root / 'gid'
    for old in ids[:-3]:
        assert not (game_dir / f'backup_{old}.zip').exists()


def test_manifest_survives_unreadable_file(tmp_path, caplog):
    snaps = tmp_path / 'snaps'
    game_dir = snaps / 'gid'
    game_dir.mkdir(parents=True)
    (game_dir / 'manifest.json').write_text('not json {', encoding='utf-8')
    # Should not raise; falls back to empty manifest
    assert sg.list_backups(snaps, 'gid') == []


def test_game_id_with_unsafe_chars_is_sanitized(tmp_path):
    save_dir = tmp_path / 'sv'
    _make_save(save_dir)
    rec = sg.backup(tmp_path / 'snaps', '../weird/id::!', [str(save_dir)])
    assert rec is not None
    # The actual on-disk folder must not contain path-traversal characters
    children = list((tmp_path / 'snaps').iterdir())
    assert children, 'a sanitized directory should exist'
    assert all('..' not in c.name and '/' not in c.name and ':' not in c.name for c in children)
