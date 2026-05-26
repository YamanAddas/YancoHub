"""
YancoHub Save Guardian — detect, snapshot, list, and restore per-game save dirs.

Designed for unit testing: the heavy filesystem operations (zip/extract) accept
explicit `paths` arguments and write to a configurable `root` directory. The
detection heuristic accepts an explicit `candidate_roots` list so tests can
point it at a tmp_path tree instead of the user's real Documents folder.

Backups live as zip files under `<saves_root>/<game_id>/backup_<ts>.zip` with
a sibling `manifest.json` that records what each backup contains.

Retention: each game keeps the most recent BACKUP_KEEP backups; older ones are
evicted automatically when a new backup is taken. The "pre-restore" auto-snapshot
that restore() takes is included in that count, so a long restore/regret cycle
won't blow out disk space.
"""

import json
import logging
import os
import re
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger('yancohub.saveguardian')

BACKUP_KEEP = 10
_MAX_BACKUP_BYTES = 500 * 1024 * 1024  # 500 MB safety cap per snapshot

_INVALID_FS = re.compile(r'[^a-z0-9]+')


def _norm(name: str) -> str:
    """Lowercase + strip non-alphanumerics — for fuzzy folder matching."""
    return _INVALID_FS.sub('', (name or '').lower())


def _default_candidate_roots():
    """Common Windows save-folder roots. Returned in priority order."""
    roots = []
    docs = Path.home() / 'Documents'
    if docs.is_dir():
        roots += [docs, docs / 'My Games']
    saved = Path.home() / 'Saved Games'
    if saved.is_dir():
        roots.append(saved)
    for env in ('LOCALAPPDATA', 'APPDATA'):
        v = os.environ.get(env)
        if v:
            p = Path(v)
            if p.is_dir():
                roots.append(p)
    return roots


def detect_candidates(game_name: str, candidate_roots=None, max_results: int = 8):
    """Best-effort heuristic: find folders under common save roots whose name
    looks like the game's. Returns a list of {path, score, root} dicts ranked
    by score desc (higher = better match)."""
    if not game_name:
        return []
    target = _norm(game_name)
    if not target:
        return []
    roots = candidate_roots if candidate_roots is not None else _default_candidate_roots()

    found = []
    seen = set()
    for root in roots:
        try:
            root = Path(root)
            if not root.is_dir():
                continue
            for entry in root.iterdir():
                if not entry.is_dir():
                    continue
                norm = _norm(entry.name)
                if not norm:
                    continue
                # Score:
                #   100 — exact normalized match
                #    80 — startswith
                #    60 — substring of target (game in folder name)
                #    50 — target substring of name (folder name in game)
                score = 0
                if norm == target:
                    score = 100
                elif norm.startswith(target):
                    score = 80
                elif target in norm:
                    score = 60
                elif norm in target and len(norm) >= 4:
                    score = 50
                if score:
                    key = str(entry.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append({
                        'path': str(entry),
                        'score': score,
                        'root': str(root),
                    })
        except (PermissionError, OSError) as e:
            logger.debug("Could not scan %s: %s", root, e)
            continue
    found.sort(key=lambda f: f['score'], reverse=True)
    return found[:max_results]


# ── Backup storage ───────────────────────────────────────────────────────────

def _game_dir(saves_root: Path, game_id: str) -> Path:
    # No '.' allowed so path-traversal-style game_ids like "../foo" can't sneak
    # in. Real game_ids are always source_id-style and never legitimately contain
    # dots, so this is safely conservative.
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', game_id or 'unknown') or 'unknown'
    return Path(saves_root) / safe


def _manifest_path(game_dir: Path) -> Path:
    return game_dir / 'manifest.json'


def _load_manifest(game_dir: Path) -> dict:
    m = _manifest_path(game_dir)
    if not m.exists():
        return {'backups': []}
    try:
        return json.loads(m.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Manifest unreadable, starting fresh: %s", e)
        return {'backups': []}


def _save_manifest(game_dir: Path, manifest: dict):
    game_dir.mkdir(parents=True, exist_ok=True)
    _manifest_path(game_dir).write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def list_backups(saves_root, game_id: str):
    """Return the recorded backups for a game (newest first)."""
    game_dir = _game_dir(Path(saves_root), game_id)
    manifest = _load_manifest(game_dir)
    return list(manifest.get('backups', []))


def backup(saves_root, game_id: str, paths, label: str = '', _pre_restore: bool = False):
    """Snapshot the given save paths into a timestamped zip.

    `paths` is a list of absolute paths (files or directories). Missing entries
    are silently skipped — the manifest records what was actually captured.

    Returns the new backup record dict, or None when nothing existed to back up.
    """
    real_paths = []
    for p in paths or []:
        try:
            rp = Path(p)
            if rp.exists():
                real_paths.append(rp)
        except (TypeError, OSError):
            continue
    if not real_paths:
        return None

    game_dir = _game_dir(Path(saves_root), game_id)
    game_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    # Millisecond precision so a backup + immediate pre-restore snapshot
    # don't collide on the same second.
    backup_id = ts.strftime('%Y%m%dT%H%M%S') + f'{ts.microsecond // 1000:03d}'
    zip_path = game_dir / f'backup_{backup_id}.zip'
    # Belt-and-braces: if a collision somehow happens (clock skew, fast loops),
    # bump until we get a unique path so we never overwrite an existing zip.
    bump = 1
    while zip_path.exists():
        backup_id = ts.strftime('%Y%m%dT%H%M%S') + f'{(ts.microsecond // 1000 + bump) % 1000:03d}'
        zip_path = game_dir / f'backup_{backup_id}.zip'
        bump += 1
        if bump > 1000:
            raise RuntimeError('Could not allocate a unique backup id')

    total_bytes = 0
    files_written = 0
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for src in real_paths:
                # Each top-level path gets its own subfolder inside the zip
                # using a sanitized version of its absolute path so restore
                # can reconstruct multiple roots without collisions.
                root_label = re.sub(r'[^A-Za-z0-9_.-]', '_', str(src.resolve()))
                if src.is_file():
                    arc = f'{root_label}/{src.name}'
                    zf.write(src, arc)
                    total_bytes += src.stat().st_size
                    files_written += 1
                    if total_bytes > _MAX_BACKUP_BYTES:
                        raise RuntimeError(f'Snapshot exceeded {_MAX_BACKUP_BYTES // (1024 * 1024)} MB cap')
                else:
                    for f in src.rglob('*'):
                        if not f.is_file():
                            continue
                        arc = f'{root_label}/{f.relative_to(src).as_posix()}'
                        zf.write(f, arc)
                        total_bytes += f.stat().st_size
                        files_written += 1
                        if total_bytes > _MAX_BACKUP_BYTES:
                            raise RuntimeError(f'Snapshot exceeded {_MAX_BACKUP_BYTES // (1024 * 1024)} MB cap')
    except Exception:
        # Clean up partial zip on any failure so we don't leave a corrupt artifact.
        try: zip_path.unlink(missing_ok=True)
        except Exception: pass
        raise

    manifest = _load_manifest(game_dir)
    record = {
        'id': backup_id,
        'created_at': ts.isoformat(),
        'paths': [str(p.resolve()) for p in real_paths],
        'size_bytes': total_bytes,
        'files': files_written,
        'label': str(label or '')[:120],
        'pre_restore': bool(_pre_restore),
    }
    manifest.setdefault('backups', []).append(record)
    # Sort newest-first, then evict beyond the retention window.
    manifest['backups'].sort(key=lambda b: b['id'], reverse=True)
    keep, evict = manifest['backups'][:BACKUP_KEEP], manifest['backups'][BACKUP_KEEP:]
    for old in evict:
        try:
            (game_dir / f'backup_{old["id"]}.zip').unlink(missing_ok=True)
        except OSError as e:
            logger.debug("Could not evict %s: %s", old.get('id'), e)
    manifest['backups'] = keep
    _save_manifest(game_dir, manifest)
    return record


def restore(saves_root, game_id: str, backup_id: str):
    """Restore a backup. Auto-snapshots the current state first (pre_restore=True)
    so the operation is reversible. Returns {restored: backup_record,
    pre_restore: record_or_None}."""
    game_dir = _game_dir(Path(saves_root), game_id)
    manifest = _load_manifest(game_dir)
    record = next((b for b in manifest.get('backups', []) if b['id'] == backup_id), None)
    if not record:
        raise FileNotFoundError(f'No backup {backup_id} for {game_id}')
    zip_path = game_dir / f'backup_{backup_id}.zip'
    if not zip_path.exists():
        raise FileNotFoundError(f'Archive missing for {backup_id}')

    # Pre-restore snapshot of whatever is at the saved paths right now.
    pre = None
    try:
        pre = backup(saves_root, game_id, record['paths'], label='auto: before restore',
                     _pre_restore=True)
    except Exception as e:
        logger.warning("Pre-restore snapshot failed for %s: %s", game_id, e)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Map top-level zip folders → original absolute paths (recorded in manifest)
        name_to_path = {
            re.sub(r'[^A-Za-z0-9_.-]', '_', str(Path(p).resolve())): Path(p)
            for p in record['paths']
        }
        for member in zf.infolist():
            if member.is_dir():
                continue
            parts = member.filename.split('/', 1)
            if len(parts) != 2:
                continue
            root_label, rel = parts
            dest_root = name_to_path.get(root_label)
            if dest_root is None:
                continue
            # If the original was a file, dest_root *is* the file path. If it was
            # a directory, append the relative member name.
            if dest_root.suffix and '.' in dest_root.name and not dest_root.is_dir():
                dest = dest_root
            else:
                dest = dest_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src_f, open(dest, 'wb') as out_f:
                shutil.copyfileobj(src_f, out_f)
    return {'restored': record, 'pre_restore': pre}


def delete_backup(saves_root, game_id: str, backup_id: str) -> bool:
    """Remove a single backup. Returns True if anything was deleted."""
    game_dir = _game_dir(Path(saves_root), game_id)
    manifest = _load_manifest(game_dir)
    before = len(manifest.get('backups', []))
    manifest['backups'] = [b for b in manifest.get('backups', []) if b['id'] != backup_id]
    after = len(manifest['backups'])
    try:
        (game_dir / f'backup_{backup_id}.zip').unlink(missing_ok=True)
    except OSError as e:
        logger.debug("Could not delete zip for %s: %s", backup_id, e)
    _save_manifest(game_dir, manifest)
    return after < before
