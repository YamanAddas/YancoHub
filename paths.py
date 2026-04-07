"""
YancoHub — Centralized Data Paths
Single source of truth for all user data, cache, and log directories.
Supports portable mode via a 'portable.txt' marker file next to the executable.
"""

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger('yancohub.paths')

APP_DIR = Path(__file__).parent

_APP_NAME = 'YancoHub'


def is_portable() -> bool:
    """Return True if running in portable mode (portable.txt next to exe)."""
    return (APP_DIR / 'portable.txt').exists()


def get_data_dir() -> Path:
    """User data directory (%APPDATA%/YancoHub or app dir in portable mode)."""
    if is_portable():
        return APP_DIR
    appdata = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    data_dir = appdata / _APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_cache_dir() -> Path:
    """Cache directory (%LOCALAPPDATA%/YancoHub/cache or app dir/cache in portable mode)."""
    if is_portable():
        d = APP_DIR / 'cache'
    else:
        localappdata = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        d = localappdata / _APP_NAME / 'cache'
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_dir() -> Path:
    """Log directory (%LOCALAPPDATA%/YancoHub/logs or app dir/logs in portable mode)."""
    if is_portable():
        d = APP_DIR / 'logs'
    else:
        localappdata = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        d = localappdata / _APP_NAME / 'logs'
    d.mkdir(parents=True, exist_ok=True)
    return d


def migrate_legacy_data() -> None:
    """One-time migration of data from app directory to %APPDATA%/%LOCALAPPDATA%.

    Copies files (does not move) and renames originals with .migrated suffix
    to prevent double-migration. Skips silently in portable mode.
    """
    if is_portable():
        return

    data_dir = get_data_dir()
    cache_dir = get_cache_dir()

    # Migrate userdata.json
    old_userdata = APP_DIR / 'userdata.json'
    new_userdata = data_dir / 'userdata.json'
    if old_userdata.exists() and not new_userdata.exists():
        try:
            shutil.copy2(old_userdata, new_userdata)
            old_userdata.rename(old_userdata.with_suffix('.json.migrated'))
            logger.info("Migrated userdata.json to %s", new_userdata)
        except OSError as e:
            logger.warning("Failed to migrate userdata.json: %s", e)

    # Migrate catbyte_history.json
    old_history = APP_DIR / 'catbyte_history.json'
    new_history = data_dir / 'catbyte_history.json'
    if old_history.exists() and not new_history.exists():
        try:
            shutil.copy2(old_history, new_history)
            old_history.rename(old_history.with_suffix('.json.migrated'))
            logger.info("Migrated catbyte_history.json to %s", new_history)
        except OSError as e:
            logger.warning("Failed to migrate catbyte_history.json: %s", e)

    # Migrate metadata.db (cache — copy only, don't rename original)
    old_db = APP_DIR / 'cache' / 'metadata.db'
    new_db = cache_dir / 'metadata.db'
    if old_db.exists() and not new_db.exists():
        try:
            new_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_db, new_db)
            logger.info("Migrated metadata.db to %s", new_db)
        except OSError as e:
            logger.warning("Failed to migrate metadata.db: %s", e)
