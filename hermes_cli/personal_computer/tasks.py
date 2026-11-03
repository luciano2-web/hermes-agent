"""Durable task and approval state for Hermes Personal Computer mode.

This module stores orchestration metadata only. It does not execute commands,
control a browser, or send messages. Callers must enforce identity and
authorization before invoking these methods, and must require approval before
performing external side effects.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(frozen=True)
class PersonalComputerTask:
    id: str
    title: str
    prompt: str
    requester_id: str
    source_channel: str
    status: TaskStatus
    created_at: str
    updated_at: str
    idempotency_key: str | None
    metadata: dict[str, Any]
    last_error: str | None = None


@dataclass(frozen=True)
class Approval:
    id: str
    task_id: str
    action: str
    summary: str
    status: ApprovalStatus
    requested_by: str
    requested_at: str
    resolved_by: str | None = None
    resolved_at: str | None = None
    resolution_note: str | None = None


@dataclass(frozen=True)
class TaskEvent:
    id: int
    task_id: str
    event_type: str
    message: str
    created_at: str
    details: dict[str, Any]


_ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.RUNNING: {
        TaskStatus.AWAITING_APPROVAL, TaskStatus.PAUSED, TaskStatus.FAILED,
        TaskStatus.COMPLETED, TaskStatus.CANCELLED,
    },
    TaskStatus.AWAITING_APPROVAL: {
        TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.PAUSED,
        TaskStatus.FAILED, TaskStatus.CANCELLED,
    },
    TaskStatus.PAUSED: {TaskStatus.QUEUED, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.FAILED: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskRegistry:
    """SQLite-backed registry shared by clients connected to one backend."""

    def __init__(self, database: str | Path, *, busy_timeout_ms: int = 5000) -> None:
        self.database = str(database)
        if self.database == ":memory:":
            raise ValueError("use a file-backed database so connections share task state")
        self.path = Path(self.database).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.database = str(self.path)
        self.busy_timeout_ms = max(0, int(busy_timeout_ms))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS pc_tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    requester_id TEXT NOT NULL,
                    source_channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    idempotency_key TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    last_error TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS pc_tasks_idempotency_scope
                    ON pc_tasks(requester_id, source_channel, idempotency_key)
                    WHERE idempotency_key IS NOT NULL;
                CREATE INDEX IF NOT EXISTS pc_tasks_status_updated
                    ON pc_tasks(status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS pc_tasks_requester_created
                    ON pc_tasks(requester_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS pc_approvals (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES pc_tasks(id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    resolution_note TEXT
                );
                CREATE INDEX IF NOT EXISTS pc_approvals_pending
                    ON pc_approvals(status, requested_at);
                CREATE TABLE IF NOT EXISTS pc_task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES pc_tasks(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )

    @staticmethod
    def _task(row: sqlite3.Row) -> PersonalComputerTask:
        return PersonalComputerTask(
            id=row["id"], title=row["title"], prompt=row["prompt"],
            requester_id=row["requester_id"], source_channel=row["source_channel"],
            status=TaskStatus(row["status"]), created_at=row["created_at"],
            updated_at=row["updated_at"], idempotency_key=row["idempotency_key"],
            metadata=json.loads(row["metadata_json"]), last_error=row["last_error"],
        )

    @staticmethod
    def _approval(row: sqlite3.Row) -> Approval:
        return Approval(
            id=row["id"], task_id=row["task_id"], action=row["action"],
            summary=row["summary"], status=ApprovalStatus(row["status"]),
            requested_by=row["requested_by"], requested_at=row["requested_at"],
            resolved_by=row["resolved_by"], resolved_at=row["resolved_at"],
            resolution_note=row["resolution_note"],
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> TaskEvent:
        return TaskEvent(
            id=row["id"], task_id=row["task_id"], event_type=row["event_type"],
            message=row["message"], created_at=row["created_at"],
            details=json.loads(row["details_json"]),
        )

    def create_task(
        self, *, title: str, prompt: str, requester_id: str, source_channel: str,
        idempotency_key: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> PersonalComputerTask:
        """Create a queued task or return the task created by a retried request."""
        required = {
            "title": title.strip(), "prompt": prompt.strip(),
            "requester_id": requester_id.strip(), "source_channel": source_channel.strip(),
        }
        if not all(required.values()):
            raise ValueError("title, prompt, requester_id, and source_channel are required")
        task_id, now = str(uuid.uuid4()), _now()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                existing = db.execute(
                    """SELECT * FROM pc_tasks
                    WHERE requester_id=? AND source_channel=? AND idempotency_key=?""",
                    (required["requester_id"], required["source_channel"], idempotency_key),
                ).fetchone()
                if existing:
                    db.commit()
                    return self._task(existing)
            db.execute(
                """INSERT INTO pc_tasks
                (id,title,prompt,requester_id,source_channel,status,created_at,updated_at,
                 idempotency_key,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (task_id, required["title"], required["prompt"], required["requester_id"],
                 required["source_channel"], TaskStatus.QUEUED.value, now, now,
                 idempotency_key, json.dumps(metadata or {}, ensure_ascii=False)),
            )
            self._add_event(db, task_id, "created", "Task queued", {"source_channel": source_channel})
            row = db.execute("SELECT * FROM pc_tasks WHERE id=?", (task_id,)).fetchone()
            db.commit()
            return self._task(row)

    def get_task(self, task_id: str) -> PersonalComputerTask | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM pc_tasks WHERE id=?", (task_id,)).fetchone()
            return self._task(row) if row else None

    def list_tasks(
        self, *, requester_id: str | None = None,
        statuses: Iterable[TaskStatus] | None = None, limit: int = 100,
    ) -> list[PersonalComputerTask]:
        limit = max(1, min(int(limit), 500))
        clauses: list[str] = []
        values: list[Any] = []
        if requester_id:
            clauses.append("requester_id=?")
            values.append(requester_id)
        status_values = [s.value for s in statuses] if statuses is not None else []
        if status_values:
            clauses.append("status IN (" + ",".join("?" for _ in status_values) + ")")
            values.extend(status_values)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as db:
            rows = db.execute(
                f"SELECT * FROM pc_tasks{where} ORDER BY updated_at DESC LIMIT ?",
                (*values, limit),
            ).fetchall()
            return [self._task(row) for row in rows]

    def transition(
        self, task_id: str, status: TaskStatus, *, actor_id: str,
        message: str | None = None, last_error: str | None = None,
    ) -> PersonalComputerTask:
        """Validate a state change and add an auditable event."""
        if not actor_id.strip():
            raise ValueError("actor_id is required")
        now = _now()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM pc_tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(task_id)
            current = TaskStatus(row["status"])
            if status == current:
                db.commit()
                return self._task(row)
            if status not in _ALLOWED_TRANSITIONS[current]:
                db.rollback()
                raise ValueError(f"invalid task transition: {current.value} -> {status.value}")
            db.execute(
                "UPDATE pc_tasks SET status=?,updated_at=?,last_error=? WHERE id=?",
                (status.value, now, last_error, task_id),
            )
            self._add_event(
                db, task_id, "status_changed",
                message or f"Task status changed to {status.value}",
                {"from": current.value, "to": status.value, "actor_id": actor_id},
            )
            updated = db.execute("SELECT * FROM pc_tasks WHERE id=?", (task_id,)).fetchone()
            db.commit()
            return self._task(updated)

    def request_approval(
        self, task_id: str, *, action: str, summary: str, requested_by: str,
    ) -> Approval:
        """Record an approval request; this method never executes the action."""
        if not action.strip() or not summary.strip() or not requested_by.strip():
            raise ValueError("action, summary, and requested_by are required")
        approval_id, now = str(uuid.uuid4()), _now()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT status FROM pc_tasks WHERE id=?", (task_id,)).fetchone()
            if task is None:
                db.rollback()
                raise KeyError(task_id)
            if TaskStatus(task["status"]) in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
                db.rollback()
                raise ValueError("cannot request approval for a terminal task")
            db.execute(
                """INSERT INTO pc_approvals
                (id,task_id,action,summary,status,requested_by,requested_at)
                VALUES (?,?,?,?,?,?,?)""",
                (approval_id, task_id, action, summary, ApprovalStatus.PENDING.value,
                 requested_by, now),
            )
            db.execute(
                "UPDATE pc_tasks SET status=?,updated_at=? WHERE id=?",
                (TaskStatus.AWAITING_APPROVAL.value, now, task_id),
            )
            self._add_event(
                db, task_id, "approval_requested", summary,
                {"approval_id": approval_id, "action": action, "requested_by": requested_by},
            )
            row = db.execute("SELECT * FROM pc_approvals WHERE id=?", (approval_id,)).fetchone()
            db.commit()
            return self._approval(row)

    def resolve_approval(
        self, approval_id: str, *, approved: bool, resolved_by: str, note: str | None = None,
    ) -> Approval:
        """Record a human decision; the caller must still enforce that decision."""
        if not resolved_by.strip():
            raise ValueError("resolved_by is required")
        now = _now()
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM pc_approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(approval_id)
            if ApprovalStatus(row["status"]) is not ApprovalStatus.PENDING:
                db.rollback()
                raise ValueError("approval has already been resolved")
            db.execute(
                """UPDATE pc_approvals SET status=?,resolved_by=?,resolved_at=?,resolution_note=?
                WHERE id=?""",
                (status.value, resolved_by, now, note, approval_id),
            )
            self._add_event(
                db, row["task_id"], "approval_resolved",
                "Approval approved" if approved else "Approval denied",
                {"approval_id": approval_id, "resolved_by": resolved_by, "note": note},
            )
            # Keep the task blocked while any other approval is still pending.
            remaining = db.execute(
                "SELECT COUNT(*) FROM pc_approvals WHERE task_id=? AND status=? AND id<>?",
                (row["task_id"], ApprovalStatus.PENDING.value, approval_id),
            ).fetchone()[0]
            if remaining == 0:
                # A later approval must never override an earlier denial on the
                # same task. Resume only when every approval was granted.
                denied = db.execute(
                    "SELECT COUNT(*) FROM pc_approvals WHERE task_id=? AND status=?",
                    (row["task_id"], ApprovalStatus.DENIED.value),
                ).fetchone()[0]
                next_task_status = TaskStatus.PAUSED if denied else TaskStatus.QUEUED
                task_row = db.execute(
                    "SELECT status FROM pc_tasks WHERE id=?", (row["task_id"],)
                ).fetchone()
                current_task_status = TaskStatus(task_row["status"])
                if current_task_status is TaskStatus.AWAITING_APPROVAL:
                    db.execute(
                        "UPDATE pc_tasks SET status=?,updated_at=? WHERE id=?",
                        (next_task_status.value, now, row["task_id"]),
                    )
                    self._add_event(
                        db, row["task_id"], "status_changed",
                        f"Task status changed to {next_task_status.value}",
                        {"from": current_task_status.value, "to": next_task_status.value,
                         "actor_id": resolved_by, "approval_id": approval_id},
                    )
            updated = db.execute("SELECT * FROM pc_approvals WHERE id=?", (approval_id,)).fetchone()
            db.commit()
            return self._approval(updated)

    def list_approvals(
        self, *, status: ApprovalStatus | None = ApprovalStatus.PENDING, limit: int = 100,
    ) -> list[Approval]:
        limit = max(1, min(int(limit), 500))
        with closing(self._connect()) as db:
            if status is None:
                rows = db.execute(
                    "SELECT * FROM pc_approvals ORDER BY requested_at DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM pc_approvals WHERE status=? ORDER BY requested_at DESC LIMIT ?",
                    (status.value, limit),
                ).fetchall()
            return [self._approval(row) for row in rows]

    def events(self, task_id: str, *, limit: int = 200) -> list[TaskEvent]:
        limit = max(1, min(int(limit), 1000))
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM pc_task_events WHERE task_id=? ORDER BY id ASC LIMIT ?",
                (task_id, limit),
            ).fetchall()
            return [self._event(row) for row in rows]

    @staticmethod
    def _add_event(
        db: sqlite3.Connection, task_id: str, event_type: str,
        message: str, details: dict[str, Any],
    ) -> None:
        db.execute(
            """INSERT INTO pc_task_events(task_id,event_type,message,created_at,details_json)
            VALUES (?,?,?,?,?)""",
            (task_id, event_type, message, _now(), json.dumps(details, ensure_ascii=False)),
        )
