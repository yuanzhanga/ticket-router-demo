import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings


def _db_path() -> str:
    path = Path(get_settings().database_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                team TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason TEXT NOT NULL,
                needs_review INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def insert_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tickets
            (content, category, priority, team, action, confidence, reason,
             needs_review, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket["content"],
                ticket["category"],
                ticket["priority"],
                ticket["team"],
                ticket["action"],
                ticket["confidence"],
                ticket["reason"],
                int(ticket["needs_review"]),
                ticket["source"],
                created_at,
            ),
        )
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)


def list_tickets(limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_stats() -> dict[str, Any]:
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()["count"]
        review = conn.execute(
            "SELECT COUNT(*) AS count FROM tickets WHERE needs_review = 1"
        ).fetchone()["count"]
        grouped = conn.execute(
            "SELECT team, COUNT(*) AS count FROM tickets GROUP BY team ORDER BY count DESC"
        ).fetchall()
        return {
            "total": total,
            "needs_review": review,
            "auto_routed": total - review,
            "by_team": {row["team"]: row["count"] for row in grouped},
        }

