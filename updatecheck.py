"""
YancoHub — Update Checker
Checks GitHub Releases API for newer versions in a background thread.
"""

import re
import logging
import threading

import requests

from constants import VERSION, HTTP_TIMEOUT_SHORT, GITHUB_REPO

logger = logging.getLogger('yancohub.updatecheck')

_update_info = None
_update_lock = threading.Lock()


def _parse_version(v: str) -> tuple:
    """Parse 'x.y.z' (with optional 'v' prefix) into (x, y, z) tuple."""
    m = re.match(r'v?(\d+)\.(\d+)\.(\d+)', v.strip())
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _is_newer(remote: str, local: str) -> bool:
    """Return True if remote version is newer than local."""
    return _parse_version(remote) > _parse_version(local)


def check_for_update() -> dict | None:
    """Check GitHub for a newer release. Returns info dict or None."""
    try:
        url = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
        resp = requests.get(url, timeout=HTTP_TIMEOUT_SHORT, headers={
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': f'YancoHub/{VERSION}',
        })
        if resp.status_code != 200:
            logger.debug("Update check: GitHub returned %d", resp.status_code)
            return None

        data = resp.json()
        tag = data.get('tag_name', '')
        if not tag:
            return None

        if _is_newer(tag, VERSION):
            return {
                'current_version': VERSION,
                'latest_version': tag.lstrip('v'),
                'tag': tag,
                'url': data.get('html_url', ''),
                'name': data.get('name', ''),
                'body': (data.get('body', '') or '')[:500],
            }
        return None

    except Exception as e:
        logger.debug("Update check failed: %s", e)
        return None


def start_update_check() -> None:
    """Fire the update check in a background daemon thread."""
    def _worker():
        global _update_info
        result = check_for_update()
        with _update_lock:
            _update_info = result
        if result:
            logger.info("Update available: %s → %s", VERSION, result['latest_version'])

    t = threading.Thread(target=_worker, name='update-check', daemon=True)
    t.start()


def get_update_info() -> dict | None:
    """Thread-safe access to the latest update check result."""
    with _update_lock:
        return _update_info
