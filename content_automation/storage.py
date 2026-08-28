"""Persistência da fila de conteúdo (SQLite)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from content_automation.models import ContentStatus, QueueItem


class ContentQueue:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS content_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    scheduled_for TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    script TEXT DEFAULT '',
                    cta TEXT DEFAULT '',
                    trend_score REAL DEFAULT 0,
                    video_path TEXT DEFAULT '',
                    publish_url TEXT DEFAULT '',
                    retries INTEGER DEFAULT 0,
                    error TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_queue_status ON content_queue(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_queue_scheduled ON content_queue(scheduled_for)"
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_item(self, row: sqlite3.Row) -> QueueItem:
        return QueueItem(
            id=row["id"],
            status=ContentStatus(row["status"]),
            topic=row["topic"],
            scheduled_for=row["scheduled_for"],
            title=row["title"] or "",
            script=row["script"] or "",
            cta=row["cta"] or "",
            trend_score=float(row["trend_score"] or 0),
            video_path=row["video_path"] or "",
            publish_url=row["publish_url"] or "",
            retries=int(row["retries"] or 0),
            error=row["error"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )

    def enqueue(self, *, topic: str, scheduled_for: str, trend_score: float = 0.0) -> QueueItem:
        now = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO content_queue (
                    status, topic, scheduled_for, trend_score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ContentStatus.PENDING.value, topic, scheduled_for, trend_score, now, now),
            )
            item_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM content_queue WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row)

    def has_slot(self, scheduled_for: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM content_queue WHERE scheduled_for = ? LIMIT 1",
                (scheduled_for,),
            ).fetchone()
        return row is not None

    def list_by_status(self, status: ContentStatus, *, limit: int = 50) -> list[QueueItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM content_queue
                WHERE status = ?
                ORDER BY scheduled_for ASC, id ASC
                LIMIT ?
                """,
                (status.value, limit),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def get(self, item_id: int) -> QueueItem | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM content_queue WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def update_item(self, item_id: int, **fields: object) -> QueueItem:
        allowed = {
            "status",
            "title",
            "script",
            "cta",
            "trend_score",
            "video_path",
            "publish_url",
            "retries",
            "error",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if "status" in updates and isinstance(updates["status"], ContentStatus):
            updates["status"] = updates["status"].value
        updates["updated_at"] = self._now()

        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [item_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE content_queue SET {assignments} WHERE id = ?", values)
            row = conn.execute("SELECT * FROM content_queue WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row)

    def count_today(self, day_prefix: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM content_queue WHERE scheduled_for LIKE ?",
                (f"{day_prefix}%",),
            ).fetchone()
        return int(row["total"]) if row else 0