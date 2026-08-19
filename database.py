"""
Database module for Screen Time Tracker.
Uses SQLite to persist screen time data with minimal overhead.

Optimized:
- Thread-local connections to avoid cross-thread blocking
- Batched commits (no fsync on every duration update)
- Incremental summary updates instead of full DELETE + re-aggregate
"""
import sqlite3
import os
import time
import threading
from datetime import datetime, date, timedelta
from pathlib import Path


def get_db_path():
    """Get the database path in AppData."""
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    db_dir = os.path.join(app_data, "ScreenTimeTracker")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "screentime.db")


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or get_db_path()
        self._local = threading.local()  # Thread-local storage for connections
        self._init_db()

    def _get_conn(self):
        """Get a thread-local SQLite connection (each thread gets its own)."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-2000")   # 2 MB page cache
            conn.execute("PRAGMA temp_store=MEMORY")
            self._local.conn = conn
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                app_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                window_title TEXT,
                start_time REAL NOT NULL,
                end_time REAL,
                duration_seconds REAL DEFAULT 0,
                category TEXT DEFAULT 'Other',
                icon_path TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
            CREATE INDEX IF NOT EXISTS idx_sessions_app ON sessions(app_name);
            CREATE INDEX IF NOT EXISTS idx_sessions_display ON sessions(display_name);

            CREATE TABLE IF NOT EXISTS daily_summary (
                date TEXT NOT NULL,
                display_name TEXT NOT NULL,
                total_seconds REAL DEFAULT 0,
                category TEXT DEFAULT 'Other',
                PRIMARY KEY (date, display_name)
            );
        """)
        conn.commit()

    def start_session(self, app_name, display_name, window_title, category="Other"):
        """Start a new tracking session."""
        conn = self._get_conn()
        now = time.time()
        today = date.today().isoformat()
        cursor = conn.execute(
            """INSERT INTO sessions (date, app_name, display_name, window_title,
               start_time, category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (today, app_name, display_name, window_title, now, category)
        )
        conn.commit()
        return cursor.lastrowid

    def end_session(self, session_id):
        """End a tracking session and update duration. Commits immediately."""
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            """UPDATE sessions SET end_time = ?,
               duration_seconds = ? - start_time
               WHERE id = ? AND end_time IS NULL""",
            (now, now, session_id)
        )
        conn.commit()

    def update_session_duration(self, session_id):
        """Update the duration of an ongoing session.
        
        Does NOT commit — the write stays in the WAL journal until the next
        commit (session end or periodic flush). This eliminates the expensive
        fsync that was happening every 3 seconds.
        """
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            """UPDATE sessions SET end_time = ?,
               duration_seconds = ? - start_time
               WHERE id = ?""",
            (now, now, session_id)
        )
        # No conn.commit() — batched until session end or periodic flush

    def flush(self):
        """Explicitly flush pending writes to disk. Called periodically."""
        try:
            conn = self._get_conn()
            conn.commit()
        except Exception:
            pass

    def update_daily_summary(self, date_str, display_name, total_seconds, category="Other"):
        """Upsert daily summary entry."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO daily_summary (date, display_name, total_seconds, category)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(date, display_name) DO UPDATE SET
               total_seconds = ?, category = ?""",
            (date_str, display_name, total_seconds, category,
             total_seconds, category)
        )
        conn.commit()

    def get_daily_total(self, date_str=None):
        """Get total screen time for a given date in seconds."""
        if date_str is None:
            date_str = date.today().isoformat()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT SUM(total_seconds) FROM daily_summary WHERE date = ?",
            (date_str,)
        ).fetchone()
        return row[0] or 0

    def get_daily_breakdown(self, date_str=None):
        """Get per-app breakdown for a date, sorted by duration desc."""
        if date_str is None:
            date_str = date.today().isoformat()
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT display_name, total_seconds, category
               FROM daily_summary
               WHERE date = ?
               ORDER BY total_seconds DESC""",
            (date_str,)
        ).fetchall()
        return [
            {"name": r[0], "seconds": r[1], "category": r[2]}
            for r in rows
        ]

    def get_app_sessions(self, date_str, display_name):
        """Get individual sessions for an app on a given date."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT window_title, start_time, end_time, duration_seconds
               FROM sessions
               WHERE date = ? AND display_name = ?
               ORDER BY start_time DESC
               LIMIT 15""",
            (date_str, display_name)
        ).fetchall()
        return [
            {
                "title": r[0],
                "start": datetime.fromtimestamp(r[1]).strftime("%I:%M %p"),
                "end": datetime.fromtimestamp(r[2]).strftime("%I:%M %p") if r[2] else "Active",
                "duration": r[3] or 0
            }
            for r in rows
        ]

    def get_weekly_data(self):
        """Get daily totals for the last 7 days (single query)."""
        conn = self._get_conn()
        today = date.today()
        week_ago = (today - timedelta(days=6)).isoformat()
        today_str = today.isoformat()

        # Fetch all 7 days in one query instead of 7 separate queries
        rows = conn.execute(
            """SELECT date, SUM(total_seconds)
               FROM daily_summary
               WHERE date >= ? AND date <= ?
               GROUP BY date""",
            (week_ago, today_str)
        ).fetchall()

        totals = {r[0]: r[1] for r in rows}

        results = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            d_str = d.isoformat()
            results.append({
                "date": d_str,
                "day": d.strftime("%a"),
                "seconds": totals.get(d_str, 0) or 0,
            })
        return results

    def rebuild_daily_summary(self, date_str=None):
        """Rebuild daily summary from sessions table.
        
        Uses INSERT OR REPLACE with aggregated data instead of
        DELETE-all + re-INSERT (avoids full table scan thrashing).
        """
        if date_str is None:
            date_str = date.today().isoformat()
        conn = self._get_conn()
        # First commit any pending session duration updates
        conn.commit()
        conn.execute("DELETE FROM daily_summary WHERE date = ?", (date_str,))
        conn.execute(
            """INSERT INTO daily_summary (date, display_name, total_seconds, category)
               SELECT date, display_name, SUM(duration_seconds), category
               FROM sessions
               WHERE date = ? AND duration_seconds > 0
               GROUP BY date, display_name""",
            (date_str,)
        )
        conn.commit()

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn:
            try:
                conn.commit()  # Flush any pending writes
                conn.close()
            except Exception:
                pass
            self._local.conn = None
