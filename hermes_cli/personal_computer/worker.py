"""Persistent parallel execution primitives for Personal Computer mode.

This is an orchestration foundation, not a hosted cloud service. A long-running
Hermes backend can execute queued work while the client is offline; deploying a
remote backend/worker is still required for work to continue when the host itself
is powered off. Handlers are responsible for checking approval before side effects.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .tasks import PersonalComputerTask, TaskRegistry, TaskStatus

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    status: str
    result: Any = None
    error: str | None = None


TaskHandler = Callable[[PersonalComputerTask, Callable[[str, dict[str, Any] | None], None]], Any]


class PersistentTaskWorker:
    """Run queued tasks concurrently and persist progress/results in the registry DB.

    Use one worker per backend database. Task handlers should be idempotent where
    possible and must independently enforce authorization and approval checks.
    The worker never interprets a missing approval as permission.
    """

    def __init__(
        self,
        registry: TaskRegistry,
        *,
        max_parallel: int = 3,
        poll_interval: float = 2.0,
        worker_id: str | None = None,
    ) -> None:
        if max_parallel < 1 or max_parallel > 32:
            raise ValueError("max_parallel must be between 1 and 32")
        if poll_interval < 0.1:
            raise ValueError("poll_interval must be at least 0.1 seconds")
        self.registry = registry
        self.max_parallel = max_parallel
        self.poll_interval = poll_interval
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:10]}"
        self._stop = threading.Event()
        self._initialize_execution_table()

    def _connect(self):
        # Reuse the registry's configured SQLite path and timeout policy.
        return self.registry._connect()

    def _initialize_execution_table(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS pc_task_executions (
                    task_id TEXT PRIMARY KEY REFERENCES pc_tasks(id) ON DELETE CASCADE,
                    worker_id TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    progress TEXT NOT NULL DEFAULT 'Queued',
                    progress_details_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES pc_tasks(id) ON DELETE CASCADE
                )
                """
            )

    def _record_start(self, task_id: str) -> None:
        now = _now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO pc_task_executions
                    (task_id, worker_id, attempts, progress, started_at, updated_at)
                VALUES (?, ?, 1, 'Running', ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    worker_id=excluded.worker_id,
                    attempts=pc_task_executions.attempts + 1,
                    progress='Running',
                    started_at=excluded.started_at,
                    finished_at=NULL,
                    updated_at=excluded.updated_at
                """,
                (task_id, self.worker_id, now, now),
            )

    def report_progress(
        self, task_id: str, message: str, details: dict[str, Any] | None = None,
    ) -> None:
        """Persist a short progress message without storing secrets or huge payloads."""
        clean_message = str(message).strip()[:1000]
        if not clean_message:
            raise ValueError("progress message is required")
        safe_details = details or {}
        encoded = json.dumps(safe_details, ensure_ascii=False, default=str)
        if len(encoded) > 8000:
            raise ValueError("progress details must be 8000 characters or less")
        now = _now()
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE pc_task_executions
                SET progress=?, progress_details_json=?, updated_at=?
                WHERE task_id=?
                """,
                (clean_message, encoded, now, task_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"task execution has not started: {task_id}")
            db.execute(
                """INSERT INTO pc_task_events
                   (task_id,event_type,message,created_at,details_json)
                   VALUES (?,?,?,?,?)""",
                (task_id, "progress", clean_message, now, encoded),
            )

    def execution(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT task_id,worker_id,attempts,progress,progress_details_json,
                          result_json,started_at,finished_at,updated_at
                   FROM pc_task_executions WHERE task_id=?""",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "worker_id": row["worker_id"],
            "attempts": row["attempts"],
            "progress": row["progress"],
            "progress_details": json.loads(row["progress_details_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "updated_at": row["updated_at"],
        }

    def _finish(self, task: PersonalComputerTask, *, result: Any = None, error: str | None = None) -> ExecutionResult:
        now = _now()
        status = "failed" if error else "completed"
        encoded_result = json.dumps(result, ensure_ascii=False, default=str) if error is None else None
        with self._connect() as db:
            db.execute(
                """UPDATE pc_task_executions
                   SET progress=?, result_json=?, finished_at=?, updated_at=?
                   WHERE task_id=?""",
                (status.title(), encoded_result, now, now, task.id),
            )
            db.execute(
                """INSERT INTO pc_task_events
                   (task_id,event_type,message,created_at,details_json)
                   VALUES (?,?,?,?,?)""",
                (task.id, "execution_finished", status.title(), now,
                 json.dumps({"worker_id": self.worker_id, "error": error}, ensure_ascii=False)),
            )
        if error:
            self.registry.transition(
                task.id, TaskStatus.FAILED, actor_id=self.worker_id,
                message="Task execution failed", last_error=error[:2000],
            )
            return ExecutionResult(task.id, status, error=error)
        self.registry.transition(
            task.id, TaskStatus.COMPLETED, actor_id=self.worker_id,
            message="Task execution completed",
        )
        return ExecutionResult(task.id, status, result=result)

    def _run_one(self, task: PersonalComputerTask, handler: TaskHandler) -> ExecutionResult:
        try:
            current = self.registry.get_task(task.id)
            if current is None or current.status is not TaskStatus.QUEUED:
                return ExecutionResult(task.id, "skipped", error="Task is no longer queued")
            self.registry.transition(
                task.id, TaskStatus.RUNNING, actor_id=self.worker_id,
                message="Task execution started",
            )
            self._record_start(task.id)
            result = handler(task, lambda message, details=None: self.report_progress(task.id, message, details))
            # Ensure results can be persisted as JSON; default=str prevents common
            # serialization failures but does not make arbitrary objects reversible.
            json.dumps(result, ensure_ascii=False, default=str)
            return self._finish(task, result=result)
        except Exception as exc:
            logger.exception("Personal Computer task failed: %s", task.id)
            try:
                current = self.registry.get_task(task.id)
                if current and current.status is TaskStatus.RUNNING:
                    return self._finish(task, error=f"{type(exc).__name__}: {exc}")
            except Exception:
                logger.exception("Could not persist failure for task %s", task.id)
            return ExecutionResult(task.id, "failed", error=f"{type(exc).__name__}: {exc}")

    def run_pending_once(self, handler: TaskHandler) -> list[ExecutionResult]:
        """Execute the currently queued batch with a bounded number of workers."""
        queued = self.registry.list_tasks(statuses=[TaskStatus.QUEUED], limit=500)
        if not queued:
            return []
        results: list[ExecutionResult] = []
        with ThreadPoolExecutor(max_workers=self.max_parallel, thread_name_prefix="hermes-pc") as pool:
            futures: dict[Future[ExecutionResult], str] = {
                pool.submit(self._run_one, task, handler): task.id for task in queued
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    logger.exception("Unexpected worker failure for task %s", futures[future])
                    results.append(ExecutionResult(futures[future], "failed", error=str(exc)))
        return results

    def serve(self, handler: TaskHandler) -> None:
        """Poll continuously until stop() is called; suitable for a persistent backend."""
        self._stop.clear()
        while not self._stop.is_set():
            try:
                results = self.run_pending_once(handler)
                if not results:
                    self._stop.wait(self.poll_interval)
            except Exception:
                logger.exception("Personal Computer worker loop failed")
                self._stop.wait(self.poll_interval)

    def stop(self) -> None:
        """Stop polling. In-flight handlers are not forcibly terminated."""
        self._stop.set()
