from __future__ import annotations

import pytest

from agent.computer_workspace import (
    ComputerWorkspaceStore,
    InvalidTaskTransition,
    TaskNotFound,
    default_database_path,
)


def test_task_persists_status_and_ordered_events(tmp_path):
    path = tmp_path / "workspace.sqlite3"
    store = ComputerWorkspaceStore(path)
    task = store.create_task(
        channel="whatsapp",
        requester_id="paired-user-1",
        title="Prepare invoice reminder",
        summary="Draft only; do not send without approval.",
        metadata={"requires_approval": True},
    )
    assert task.status == "queued"
    store.transition(task.id, "running")
    store.append_event(task.id, "browser.navigation", message="Invoice page opened")
    store.transition(task.id, "awaiting_approval", message="Draft ready")

    restored = ComputerWorkspaceStore(path).get_task(task.id)
    assert restored.status == "awaiting_approval"
    assert restored.metadata == {"requires_approval": True}
    assert [event["kind"] for event in store.list_events(task.id)] == [
        "task.created", "task.running", "browser.navigation", "task.awaiting_approval"
    ]


def test_request_key_deduplicates_retried_messages(tmp_path):
    store = ComputerWorkspaceStore(tmp_path / "workspace.sqlite3")
    args = dict(channel="whatsapp", requester_id="paired-user-1",
                title="Review quote", request_key="whatsapp:message:123")
    first = store.create_task(**args)
    second = store.create_task(**args)
    assert second.id == first.id
    assert len(store.list_tasks()) == 1
    assert len(store.list_events(first.id)) == 1


def test_completed_task_cannot_be_reopened(tmp_path):
    store = ComputerWorkspaceStore(tmp_path / "workspace.sqlite3")
    task = store.create_task(channel="desktop", requester_id="local-user", title="Check website")
    store.transition(task.id, "running")
    store.transition(task.id, "completed")
    with pytest.raises(InvalidTaskTransition):
        store.transition(task.id, "running")


def test_missing_task_and_invalid_inputs_are_reported(tmp_path):
    store = ComputerWorkspaceStore(tmp_path / "workspace.sqlite3")
    with pytest.raises(TaskNotFound):
        store.get_task("missing")
    with pytest.raises(ValueError):
        store.list_tasks(limit=0)
    with pytest.raises(ValueError):
        store.create_task(channel="", requester_id="user", title="Task")


def test_default_database_path_respects_hermes_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert default_database_path() == tmp_path / "computer-workspace.sqlite3"
