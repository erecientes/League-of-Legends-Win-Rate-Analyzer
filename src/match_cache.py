from contextlib import contextmanager
import sqlite3
import json

from config import DB_DIR
 
# This class provides a simple caching mechanism for match data fetched from the Riot API. 
class MatchCache:
    def __init__(self, db_filename: str):
        self.db_path = str(DB_DIR / db_filename)
        self._init_db()
 
    # Context manager for database connection. Ensures that the connection is properly closed after use.
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
 
    # Initialize the database and create the matches table if it doesn't exist. 
    # The table stores match IDs, raw JSON data, and the timestamp of when the data was fetched.
    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    match_id    TEXT PRIMARY KEY,
                    match_data  TEXT NOT NULL,   
                    timeline_data TEXT NOT NULL, 
                    fetched_at  TEXT DEFAULT (datetime('now'))
                )
            """)
 
    # Check if a match ID exists in the cache. 
    def has_match(self, match_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM matches WHERE match_id = ? LIMIT 1", (match_id,)
            ).fetchone()
        return row is not None
    
    # Save a newly-fetched match to the cache. If the match ID already exists, it will be ignored.
    def save_match(self, match_id: str, match_data: dict, timeline_data: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO matches (match_id, match_data, timeline_data) VALUES (?, ?, ?)",
                (match_id, json.dumps(match_data), json.dumps(timeline_data)),
            ) 

    # Retrieve match data from the cache. Returns None if the match ID is not found.
    def get_match_data(self, match_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT match_data FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None
 
    # Retrieve timeline data from the cache. Returns None if the match ID is not found.
    def get_timeline_data(self, match_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT timeline_data FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None
 
    # Retrieve all match IDs currently stored in the cache. Returns a list of match IDs.
    def get_all_match_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT match_id FROM matches").fetchall()
        return [r[0] for r in rows]
 
    # Generator to iterate over all cached matches. Yields (match_id, match_data, timeline_data) tuples.
    def iter_matches(self):
        with self._connect() as conn:
            cursor = conn.execute("SELECT match_id, match_data, timeline_data FROM matches")
            for match_id, match_data, timeline_data in cursor:
                yield match_id, json.loads(match_data), json.loads(timeline_data)
 
    # Count the total number of matches stored in the cache. Returns an integer count.
    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]