"""SQLite audit trail of every decision and control-plane event.

Thread-safe (one connection guarded by a lock, WAL journal). Use
":memory:" for tests. Events are append-only.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path

from src.core.decision.states import Decision

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    from_state TEXT, to_state TEXT,
    from_rung INTEGER, to_rung INTEGER,
    action TEXT,
    reasons TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
"""
COLUMNS = ("id", "ts", "kind", "from_state", "to_state", "from_rung",
           "to_rung", "action", "reasons", "detail")


class DecisionLog:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            if str(path) != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)

    def record_decision(self, d: Decision) -> None:
        """Log a decision that changed the rung or the state."""
        self._insert("decision", d.timestamp, d.prev_state.value,
                     d.state.value, d.prev_rung, d.rung, d.action,
                     list(d.reasons), d.signals)

    def record_event(self, kind: str, detail: dict | None = None,
                     ts: float | None = None) -> None:
        """Log a non-decision event (swap_done, camera_reconnect, ...)."""
        self._insert(kind, ts or time.time(), None, None, None, None,
                     None, [], detail or {})

    def _insert(self, kind, ts, fs, ts_state, fr, tr, action, reasons, detail):
        with self._lock:
            self._db.execute(
                "INSERT INTO events (ts, kind, from_state, to_state, from_rung,"
                " to_rung, action, reasons, detail) VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, kind, fs, ts_state, fr, tr, action,
                 json.dumps(reasons), json.dumps(detail)),
            )
            self._db.commit()

    def recent(self, limit: int = 50, kind: str | None = None) -> list[dict]:
        """Newest-first events as plain dicts (JSON fields decoded)."""
        query = f"SELECT {','.join(COLUMNS)} FROM events"
        args: tuple = ()
        if kind:
            query += " WHERE kind = ?"
            args = (kind,)
        query += " ORDER BY id DESC LIMIT ?"
        with self._lock:
            rows = self._db.execute(query, args + (limit,)).fetchall()
        out = []
        for row in rows:
            rec = dict(zip(COLUMNS, row))
            rec["reasons"] = json.loads(rec["reasons"] or "[]")
            rec["detail"] = json.loads(rec["detail"] or "{}")
            out.append(rec)
        return out

    def count(self, kind: str | None = None) -> int:
        query, args = "SELECT COUNT(*) FROM events", ()
        if kind:
            query, args = query + " WHERE kind = ?", (kind,)
        with self._lock:
            return self._db.execute(query, args).fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._db.close()
