"""
YancoHub Year in Review — pure-data aggregator for the local year summary.

Designed for unit testing: takes plain dict/list inputs (no app imports) and
returns a JSON-ready dict. The app's metadata_db is duck-typed — anything with
a `.get(game_id)` method that returns a metadata dict (or None) will work.

Data shape note: userdata.json stores per-game totals only — `total_seconds`,
`last_played`, `session_count`. We don't have per-session day-by-day history,
so "this year" filters on games whose `last_played` falls in the year, and we
attribute each such game's *lifetime* hours to the year. The UI is explicit
about this so users aren't misled.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone

logger = logging.getLogger('yancohub.yearsummary')


def _to_ts(value):
    """Convert a stored last_played value to a unix timestamp, or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_year_summary(year, playtime, library, metadata_db=None):
    """Build a year-in-review payload from local data.

    Args:
        year:        int — the calendar year (UTC) to summarize.
        playtime:    dict — {game_id: {'total_hours', 'last_played', 'session_count'}}
                     (the shape returned by UserData.get_playtime() with no args).
        library:     list of dicts — each with at least {id, name}; optional
                     {source, system}.
        metadata_db: optional object with a .get(game_id) method that returns a
                     metadata dict (or None). Used for the genre breakdown.

    Returns:
        A JSON-ready dict — see the bottom of this function for the shape.
    """
    year = int(year)
    year_start = datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()
    year_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp()

    by_id = {g['id']: g for g in (library or []) if g.get('id')}

    touched = []
    for gid, s in (playtime or {}).items():
        if not isinstance(s, dict):
            continue
        last_ts = _to_ts(s.get('last_played'))
        if last_ts is None or not (year_start <= last_ts < year_end):
            continue
        entry = by_id.get(gid)
        if not entry:
            continue
        hours = float(s.get('total_hours') or 0.0)
        if hours <= 0:
            continue
        last_iso = datetime.fromtimestamp(last_ts, timezone.utc).strftime('%Y-%m-%d')
        touched.append({
            'game_id': gid,
            'name': entry.get('name', '(unknown)'),
            'source': entry.get('source', ''),
            'system': entry.get('system') or entry.get('source', '') or 'other',
            'hours': round(hours, 1),
            'last_played': last_ts,
            'last_played_iso': last_iso,
            'artwork_url': f'/api/artwork/{gid}/cover',
        })

    touched.sort(key=lambda g: (g['hours'], g['last_played']), reverse=True)

    top_games = touched[:5]
    hours_total = round(sum(g['hours'] for g in touched), 1)

    # By system / store
    sys_counts = Counter()
    sys_hours = defaultdict(float)
    for g in touched:
        sys_counts[g['system']] += 1
        sys_hours[g['system']] += g['hours']
    by_system = [
        {'system': s, 'count': c, 'hours': round(sys_hours[s], 1)}
        for s, c in sys_counts.most_common()
    ]

    # By month (12 buckets, last_played → month)
    by_month = []
    month_buckets = {}
    for m in range(1, 13):
        month_buckets[m] = {'hours': 0.0, 'games': 0, 'top_game': None, '_top_hours': 0.0}
    for g in touched:
        m = datetime.fromtimestamp(g['last_played'], timezone.utc).month
        b = month_buckets[m]
        b['hours'] += g['hours']
        b['games'] += 1
        if g['hours'] > b['_top_hours']:
            b['_top_hours'] = g['hours']
            b['top_game'] = g['name']
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for m in range(1, 13):
        b = month_buckets[m]
        by_month.append({
            'month': m,
            'label': month_labels[m - 1],
            'hours': round(b['hours'], 1),
            'games': b['games'],
            'top_game': b['top_game'],
        })

    # By genre (from metadata_db)
    genre_buckets = defaultdict(float)
    if metadata_db is not None:
        for g in touched:
            try:
                meta = metadata_db.get(g['game_id'])
            except Exception as e:
                logger.debug("metadata lookup failed for %s: %s", g['game_id'], e)
                meta = None
            if not meta:
                continue
            raw = meta.get('genre') or ''
            # Genres are often comma-separated — take the first as the primary
            primary = raw.split(',')[0].strip()
            if primary:
                genre_buckets[primary] += g['hours']
    by_genre = sorted(
        ({'genre': k, 'hours': round(v, 1)} for k, v in genre_buckets.items()),
        key=lambda x: x['hours'], reverse=True,
    )[:6]

    by_date = sorted(touched, key=lambda g: g['last_played'])
    first_play = by_date[0] if by_date else None
    last_play = by_date[-1] if by_date else None

    # All-time totals across the whole library (any session with hours)
    all_time_hours = 0.0
    all_time_games = 0
    for s in (playtime or {}).values():
        if not isinstance(s, dict):
            continue
        hours = float(s.get('total_hours') or 0.0)
        if hours > 0:
            all_time_hours += hours
            all_time_games += 1

    return {
        'year': year,
        'games_touched': len(touched),
        'hours_total': hours_total,
        'top_games': top_games,
        'by_system': by_system,
        'by_month': by_month,
        'by_genre': by_genre,
        'first_play': first_play,
        'last_play': last_play,
        'all_time': {
            'hours': round(all_time_hours, 1),
            'games': all_time_games,
        },
    }
