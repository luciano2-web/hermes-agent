"""Persistent, platform-neutral task state for Hermes Personal Computer mode.

This is a storage primitive, not a computer driver or HTTP endpoint. Desktop,
mobile, and messaging adapters can share task IDs and status semantics without
creating a second terminal/browser runtime. Callers must pass redacted summaries.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

TaskStatus = Literal[
    "queued", "running", "awaiting_approval", "paused",
    "failed", "completed", "cancelled",
]

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "paused", "cancelled", "failed"}),
    "running": frozenset({"awaiting_approval", "paused", "failed", "completed", "cancelled"}),
    "awaiting_approval": frozenset({"running", "paused", "cancelled", "failed"}),
    "paused": frozenset({"queued", "running", "cancelled", "failed"}),
    "failed": frozenset({"queued"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def default_database_path() -> Path:
    """Use the active Hermes home, respecting HERMES_HOME overrides."""
    return Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser() / "computer-workspace.sqlite3"


@dataclass(frozen=True)
class ComputerTask:
    id: str
    request_key: str | None
    channel: str
    requester_id: str
    title: str
    summary: str
    status: TaskStatus
    created_at: str
    updated_at: str
    metadata: dict[str, Any]


class InvalidTaskTransition(ValueError):
    """Raised when a task status change is not permitted."""


class TaskNotFound(LookupError):
    """Raised when a requested task ID does not exist."""


class ComputerWorkspaceStore:
    """SQLite task ledger with idempotent creation and an append-only event log."""

    def __init__(self, database: str | Path | None = None) -> None:
        self.path = Path(database) if database is not None else default_database_path()
        self._lock = threading.RLock()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA busy_timeout = 10000")
            yield db
        finally:
            db.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            if str(self.path) != ":memory:":
                db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS computer_tasks (
                    id TEXT PRIMARY KEY,
                    request_key TEXT UNIQUE,
                    channel TEXT NOT NULL,
                    requester_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK (status IN
                      ('queued','running','awaiting_approval','paused','failed','completed','cancelled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS computer_tasks_status_updated
                    ON computer_tasks(status, updated_at DESC);
                CREATE TABLE IF NOT EXISTS computer_task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES computer_tasks(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    data_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS computer_task_events_task_id
                    ON computer_task_events(task_id, id);
            """)

    @staticmethod
    def _decode(row: sqlite3.Row) -> ComputerTask:
        return ComputerTask(
            id=row["id"], request_key=row["request_key"], channel=row["channel"],
            requester_id=row["requester_id"], title=row["title"], summary=row["summary"],
            status=row["status"], created_at=row["created_at"], updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _event(db: sqlite3.Connection, task_id: str, kind: str, message: str, data: dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO computer_task_events (task_id, kind, message, data_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, kind, message, json.dumps(data, ensure_ascii=False, sort_keys=True), _now()),
        )

    def create_task(
        self, *, channel: str, requester_id: str, title: str, summary: str = "",
        request_key: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> ComputerTask:
        """Create a queued task, returning the existing task for duplicate request keys."""
        if not all(value.strip() for value in (channel, requester_id, title)):
            raise ValueError("channel, requester_id, and title must be non-empty")
        if request_key is not None and not request_key.strip():
            raise ValueError("request_key must be non-empty when provided")
        now, task_id = _now(), uuid.uuid4().hex
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if request_key is not None:
                    existing = db.execute(
                        "SELECT * FROM computer_tasks WHERE request_key = ?", (request_key,)
                    ).fetchone()
                    if existing is not None:
                        db.execute("COMMIT")
                        return self._decode(existing)
                db.execute(
                    """INSERT INTO computer_tasks
                    (id, request_key, channel, requester_id, title, summary, status,
                     created_at, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)""",
                    (task_id, request_key, channel.strip(), requester_id.strip(), title.strip(),
                     summary.strip(), now, now, metadata_json),
                )
                self._event(db, task_id, "task.created", "Task queued", {})
                row = db.execute("SELECT * FROM computer_tasks WHERE id = ?", (task_id,)).fetchone()
                db.execute("COMMIT")
                return self._decode(row)
            except Exception:
                db.execute("ROLLBACK")
                raise

    def get_task(self, task_id: str) -> ComputerTask:
        with self._connect() as db:
            row = db.execute("SELECT * FROM computer_tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(task_id)
        return self._decode(row)

    def list_tasks(self, *, status: str | None = None, limit: int = 100) -> list[ComputerTask]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        with self._connect() as db:
            if status is None:
                rows = db.execute(
                    "SELECT * FROM computer_tasks ORDER BY updated_at DESC, id LIMIT ?", (limit,)
                ).fetchall()
            else:
                if status not in _ALLOWED_TRANSITIONS:
                    raise ValueError(f"unknown task status: {status}")
                rows = db.execute(
                    "SELECT * FROM computer_tasks WHERE status = ? ORDER BY updated_at DESC, id LIMIT ?",
                    (status, limit),
                ).fetchall()
        return [self._decode(row) for row in rows]

    def transition(
        self, task_id: str, status: TaskStatus, *, message: str = "",
        event_data: dict[str, Any] | None = None,
    ) -> ComputerTask:
        """Atomically change status and append an event."""
        if status not in _ALLOWED_TRANSITIONS:
            raise ValueError(f"unknown task status: {status}")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT * FROM computer_tasks WHERE id = ?", (task_id,)).fetchone()
                if row is None:
                    raise TaskNotFound(task_id)
                old_status = row["status"]
                if status not in _ALLOWED_TRANSITIONS[old_status]:
                    raise InvalidTaskTransition(f"cannot transition task from {old_status!r} to {status!r}")
                db.execute(
                    "UPDATE computer_tasks SET status = ?, updated_at = ? WHERE id = ?",
                    (status, _now(), task_id),
                )
                self._event(db, task_id, f"task.{status}", message, event_data or {})
                updated = db.execute("SELECT * FROM computer_tasks WHERE id = ?", (task_id,)).fetchone()
                db.execute("COMMIT")
                return self._decode(updated)
            except Exception:
                db.execute("ROLLBACK")
                raise

    def append_event(
        self, task_id: str, kind: str, *, message: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Append a redacted progress/audit event without changing status."""
        if not kind.strip():
            raise ValueError("event kind must be non-empty")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM computer_tasks WHERE id = ?", (task_id,)).fetchone() is None:
                    raise TaskNotFound(task_id)
                self._event(db, task_id, kind.strip(), message, data or {})
                db.execute("UPDATE computer_tasks SET updated_at = ? WHERE id = ?", (_now(), task_id))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def list_events(self, task_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as db:
            if db.execute("SELECT 1 FROM computer_tasks WHERE id = ?", (task_id,)).fetchone() is None:
                raise TaskNotFound(task_id)
            rows = db.execute(
                "SELECT kind, message, data_json, created_at FROM computer_task_events "
                "WHERE task_id = ? ORDER BY id DESC LIMIT ?", (task_id, limit)
            ).fetchall()
        return [
            {"kind": row["kind"], "message": row["message"],
             "data": json.loads(row["data_json"]), "created_at": row["created_at"]}
            for row in reversed(rows)
        ]
