"""
YancoHub Metadata Engine — Auto-fetches game metadata from free public APIs.

Sources:
  - IGDB (Twitch) — descriptions, genres, developer, publisher, ratings
  - LibRetro thumbnails — retro game cover art URLs
  - SteamGridDB — PC game artwork
  - Steam CDN — Steam game artwork (direct URLs)
"""

import os
import re
import json
import time
import logging
import sqlite3
import requests
from pathlib import Path

logger = logging.getLogger('yancohub.metadata')

DB_PATH = Path(__file__).parent / 'cache' / 'metadata.db'

# ── LibRetro thumbnail system name mapping ──────────────────────────────────

LIBRETRO_SYSTEMS = {
    'nes':          'Nintendo - Nintendo Entertainment System',
    'snes':         'Nintendo - Super Nintendo Entertainment System',
    'gb':           'Nintendo - Game Boy',
    'gbc':          'Nintendo - Game Boy Color',
    'gba':          'Nintendo - Game Boy Advance',
    'n64':          'Nintendo - Nintendo 64',
    'nds':          'Nintendo - Nintendo DS',
    'megadrive':    'Sega - Mega Drive - Genesis',
    'mastersystem': 'Sega - Master System - Mark III',
    'gamegear':     'Sega - Game Gear',
    'atari2600':    'Atari - 2600',
    'psx':          'Sony - PlayStation',
    'ps2':          'Sony - PlayStation 2',
    'psp':          'Sony - PlayStation Portable',
    'dreamcast':    'Sega - Dreamcast',
    'saturn':       'Sega - Saturn',
    'gamecube':     'Nintendo - GameCube',
    'wii':          'Nintendo - Wii',
    'neogeo':       'SNK - Neo Geo',
    'ngp':          'SNK - Neo Geo Pocket',
    'fbneo':        'FBNeo - Arcade Games',
    'cps1':         'FBNeo - Arcade Games',
    'cps2':         'FBNeo - Arcade Games',
    'cps3':         'FBNeo - Arcade Games',
    'mame':         'MAME',
}

LIBRETRO_THUMB_BASE = 'https://thumbnails.libretro.com'

# ── Steam CDN ───────────────────────────────────────────────────────────────

STEAM_CDN = 'https://cdn.cloudflare.steamstatic.com/steam/apps'

# ── IGDB (via public proxy or direct) ───────────────────────────────────────

# IGDB requires Twitch OAuth for direct access. We use a search-based approach
# with their public-facing data when available, or fall back to other sources.

# ── Database ────────────────────────────────────────────────────────────────

class MetadataDB:
    """Local SQLite cache for game metadata."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_metadata (
                game_id TEXT PRIMARY KEY,
                title TEXT,
                developer TEXT,
                publisher TEXT,
                genre TEXT,
                release_year INTEGER,
                description TEXT,
                rating REAL,
                rating_count INTEGER,
                cover_url TEXT,
                screenshot_url TEXT,
                logo_url TEXT,
                players TEXT,
                cached_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artwork_cache (
                game_id TEXT,
                art_type TEXT,
                local_path TEXT,
                remote_url TEXT,
                cached_at REAL,
                PRIMARY KEY (game_id, art_type)
            )
        """)
        conn.commit()
        conn.close()

    def get(self, game_id):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_metadata WHERE game_id = ?", (game_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def put(self, game_id, **kwargs):
        conn = sqlite3.connect(str(self.db_path))
        kwargs['game_id'] = game_id
        kwargs['cached_at'] = time.time()

        cols = list(kwargs.keys())
        placeholders = ','.join(['?'] * len(cols))
        updates = ','.join([f'{c}=excluded.{c}' for c in cols if c != 'game_id'])

        conn.execute(
            f"INSERT INTO game_metadata ({','.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(game_id) DO UPDATE SET {updates}",
            [kwargs[c] for c in cols]
        )
        conn.commit()
        conn.close()

    def get_artwork(self, game_id, art_type):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM artwork_cache WHERE game_id = ? AND art_type = ?",
            (game_id, art_type)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def put_artwork(self, game_id, art_type, local_path='', remote_url=''):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT OR REPLACE INTO artwork_cache (game_id, art_type, local_path, remote_url, cached_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (game_id, art_type, local_path, remote_url, time.time())
        )
        conn.commit()
        conn.close()

    def get_stats(self):
        conn = sqlite3.connect(str(self.db_path))
        meta_count = conn.execute("SELECT COUNT(*) FROM game_metadata").fetchone()[0]
        art_count = conn.execute("SELECT COUNT(*) FROM artwork_cache").fetchone()[0]
        conn.close()
        return {'metadata_entries': meta_count, 'artwork_entries': art_count}


# ── Metadata Fetcher ────────────────────────────────────────────────────────

class MetadataFetcher:
    """Fetches and caches game metadata from multiple sources."""

    def __init__(self):
        self.db = MetadataDB()
        self._session = requests.Session()
        self._session.headers['User-Agent'] = 'YancoHub/1.0'

    def get_metadata(self, game_id, game_name, source='', system=''):
        """Get metadata for a game, fetching if not cached."""
        cached = self.db.get(game_id)
        if cached and cached.get('description'):
            return cached

        # Fetch from appropriate source
        metadata = None

        if source == 'steam':
            appid = game_id.replace('steam_', '')
            metadata = self._fetch_steam_metadata(appid, game_name)

        if not metadata or not metadata.get('description'):
            metadata = self._fetch_wikipedia_summary(game_name)

        if metadata:
            self.db.put(game_id, **metadata)
            return self.db.get(game_id)

        # Store a minimal entry so we don't re-fetch constantly
        self.db.put(game_id, title=game_name)
        return self.db.get(game_id)

    def _fetch_steam_metadata(self, appid, game_name):
        """Fetch metadata from Steam's store API."""
        try:
            resp = self._session.get(
                f'https://store.steampowered.com/api/appdetails?appids={appid}&l=english',
                timeout=10,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            app_data = data.get(str(appid), {}).get('data', {})
            if not app_data:
                return None

            # Clean HTML from description
            desc = app_data.get('short_description', '')

            genres = '; '.join([g['description'] for g in app_data.get('genres', [])])
            devs = '; '.join(app_data.get('developers', []))
            pubs = '; '.join(app_data.get('publishers', []))

            release = app_data.get('release_date', {}).get('date', '')
            year = None
            if release:
                match = re.search(r'\b(19|20)\d{2}\b', release)
                if match:
                    year = int(match.group())

            metacritic = app_data.get('metacritic', {})
            rating = None
            if metacritic.get('score'):
                rating = round(metacritic['score'] / 20, 1)  # Convert 0-100 to 0-5

            return {
                'title': app_data.get('name', game_name),
                'developer': devs,
                'publisher': pubs,
                'genre': genres,
                'release_year': year,
                'description': desc,
                'rating': rating,
                'players': str(app_data.get('recommendations', {}).get('total', '')),
            }
        except Exception as e:
            logger.debug(f"Steam metadata fetch failed for {appid}: {e}")
            return None

    def _fetch_wikipedia_summary(self, game_name):
        """Fetch a short summary from Wikipedia's API (CC-BY-SA)."""
        try:
            # Search for the game
            search_name = f"{game_name} video game"
            resp = self._session.get(
                'https://en.wikipedia.org/api/rest_v1/page/summary/' +
                requests.utils.quote(search_name.replace(' ', '_')),
                timeout=8,
            )

            if resp.status_code != 200:
                # Try without "video game" suffix
                resp = self._session.get(
                    'https://en.wikipedia.org/api/rest_v1/page/summary/' +
                    requests.utils.quote(game_name.replace(' ', '_')),
                    timeout=8,
                )

            if resp.status_code != 200:
                return None

            data = resp.json()
            extract = data.get('extract', '')

            if not extract or len(extract) < 50:
                return None

            # Trim to reasonable length
            if len(extract) > 500:
                # Cut at last sentence boundary before 500 chars
                cut = extract[:500].rfind('.')
                if cut > 200:
                    extract = extract[:cut + 1]

            return {
                'title': game_name,
                'description': extract,
            }
        except Exception as e:
            logger.debug(f"Wikipedia fetch failed for {game_name}: {e}")
            return None

    def enrich_games(self, games, batch_delay=0.2):
        """Enrich a list of games with metadata. Non-blocking, skips cached."""
        enriched = 0
        for game in games:
            game_id = game.get('id', '')
            if not game_id:
                continue

            cached = self.db.get(game_id)
            if cached and cached.get('cached_at'):
                continue

            try:
                self.get_metadata(
                    game_id,
                    game.get('name', ''),
                    source=game.get('source', ''),
                    system=game.get('system', ''),
                )
                enriched += 1
                if batch_delay:
                    time.sleep(batch_delay)
            except Exception as e:
                logger.debug(f"Metadata enrichment failed for {game_id}: {e}")

        logger.info(f"Enriched {enriched} games with metadata")
