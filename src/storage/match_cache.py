"""
SQLite cache for raw Riot API match and timeline JSON payloads.

Usage:
    from match_cache import MatchCache
    cache = MatchCache("matches_user.db")
    cache.save_match(match_id, match_data, timeline_data)
"""

from contextlib import contextmanager
import sqlite3
import json
from config import DB_DIR


class MatchCache:
    """SQLite cache for raw Riot match and timeline JSON payloads."""

    def __init__(self, db_filename: str):
        self.db_path = str(DB_DIR / db_filename)
        self._init_db()

    @contextmanager
    def _connect(self):
        """Context manager yielding an open database connection."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """Initialize SQLite schema if table does not exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    match_id      TEXT PRIMARY KEY,
                    match_data    TEXT NOT NULL,
                    timeline_data TEXT NOT NULL,
                    fetched_at    TEXT DEFAULT (datetime('now'))
                )
            """)

    def has_match(self, match_id: str) -> bool:
        """Check if match_id exists in the cache."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM matches WHERE match_id = ? LIMIT 1", (match_id,)
            ).fetchone()
        return row is not None

    def save_match(self, match_id: str, match_data: dict, timeline_data: dict) -> None:
        """Insert match and timeline JSON into the database."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO matches (match_id, match_data, timeline_data) VALUES (?, ?, ?)",
                (match_id, json.dumps(match_data), json.dumps(timeline_data)),
            )

    def get_match_data(self, match_id: str) -> dict | None:
        """Retrieve match JSON dict by match ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT match_data FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_timeline_data(self, match_id: str) -> dict | None:
        """Retrieve timeline JSON dict by match ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT timeline_data FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_all_match_ids(self) -> list[str]:
        """Return list of all cached match IDs."""
        with self._connect() as conn:
            rows = conn.execute("SELECT match_id FROM matches").fetchall()
        return [r[0] for r in rows]

    def iter_matches(self):
        """Yield (match_id, match_data, timeline_data) tuples from database."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT match_id, match_data, timeline_data FROM matches")
            for match_id, match_data, timeline_data in cursor:
                yield match_id, json.loads(match_data), json.loads(timeline_data)

    def count(self) -> int:
        """Return total count of cached matches."""
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
