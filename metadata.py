"""
YancoHub Metadata Engine — Auto-fetches game metadata from free public APIs.

Sources:
  - Steam Store API — descriptions, genres, developer, publisher, ratings
  - Wikipedia REST API — short summaries for non-Steam games (CC-BY-SA)

Results cached in SQLite (cache/metadata.db) to avoid repeated requests.
"""


import re
import json
import time
import logging
import sqlite3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path

logger = logging.getLogger('yancohub.metadata')

DB_PATH = Path(__file__).parent / 'cache' / 'metadata.db'

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
        with sqlite3.connect(str(self.db_path)) as conn:
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

    def get(self, game_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM game_metadata WHERE game_id = ?", (game_id,)).fetchone()
            return dict(row) if row else None

    def put(self, game_id, **kwargs):
        with sqlite3.connect(str(self.db_path)) as conn:
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



# ── Metadata Fetcher ────────────────────────────────────────────────────────

class MetadataFetcher:
    """Fetches and caches game metadata from multiple sources."""

    def __init__(self):
        self.db = MetadataDB()
        self._session = requests.Session()
        self._session.headers['User-Agent'] = 'YancoHub/1.0'
        retry = Retry(total=3, backoff_factor=1.0,
                      status_forcelist=[429, 500, 502, 503, 504])
        self._session.mount('https://', HTTPAdapter(max_retries=retry))
        self._session.mount('http://', HTTPAdapter(max_retries=retry))

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
