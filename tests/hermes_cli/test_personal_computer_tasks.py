from __future__ import annotations

import pytest

from hermes_cli.personal_computer.tasks import ApprovalStatus, TaskRegistry, TaskStatus


def make_registry(tmp_path):
    return TaskRegistry(tmp_path / "personal-computer.sqlite3")


def make_task(store, *, channel="desktop", key=None):
    return store.create_task(
        title="Review quote",
        prompt="Check whether the quote needs a reply",
        requester_id="user-1",
        source_channel=channel,
        idempotency_key=key,
    )


def test_task_survives_registry_restart(tmp_path):
    path = tmp_path / "personal-computer.sqlite3"
    task = make_task(TaskRegistry(path))
    restored = TaskRegistry(path).get_task(task.id)
    assert restored is not None
    assert restored.id == task.id
    assert restored.status is TaskStatus.QUEUED


def test_idempotency_key_prevents_duplicate_tasks(tmp_path):
    store = make_registry(tmp_path)
    first = make_task(store, channel="whatsapp", key="whatsapp:message-123")
    duplicate = store.create_task(
        title="retry", prompt="retry", requester_id="user-1",
        source_channel="whatsapp", idempotency_key="whatsapp:message-123",
    )
    assert duplicate.id == first.id
    assert len(store.list_tasks()) == 1


def test_idempotency_key_is_scoped_to_requester_and_channel(tmp_path):
    store = make_registry(tmp_path)
    first = store.create_task(
        title="Private task A", prompt="A", requester_id="user-a",
        source_channel="whatsapp", idempotency_key="message-123",
    )
    second = store.create_task(
        title="Private task B", prompt="B", requester_id="user-b",
        source_channel="whatsapp", idempotency_key="message-123",
    )
    third = store.create_task(
        title="Private task C", prompt="C", requester_id="user-a",
        source_channel="telegram", idempotency_key="message-123",
    )

    assert len({first.id, second.id, third.id}) == 3
    assert store.get_task(first.id).requester_id == "user-a"
    assert store.get_task(second.id).requester_id == "user-b"


def test_status_transition_validation(tmp_path):
    store = make_registry(tmp_path)
    task = make_task(store)
    with pytest.raises(ValueError, match="invalid task transition"):
        store.transition(task.id, TaskStatus.COMPLETED, actor_id="worker-1")


def test_approval_is_pending_until_a_human_resolves_it(tmp_path):
    store = make_registry(tmp_path)
    task = make_task(store, channel="whatsapp")
    approval = store.request_approval(
        task.id, action="send_email", summary="Send drafted reply", requested_by="hermes",
    )
    assert approval.status is ApprovalStatus.PENDING
    assert store.get_task(task.id).status is TaskStatus.AWAITING_APPROVAL
    assert store.list_approvals()[0].id == approval.id

    denied = store.resolve_approval(
        approval.id, approved=False, resolved_by="user-1", note="Needs revision",
    )
    assert denied.status is ApprovalStatus.DENIED
    assert store.get_task(task.id).status is TaskStatus.PAUSED
    event_types = [event.event_type for event in store.events(task.id)]
    assert "approval_resolved" in event_types
    assert event_types[-1] == "status_changed"


def test_approval_cannot_be_resolved_twice(tmp_path):
    store = make_registry(tmp_path)
    task = make_task(store)
    approval = store.request_approval(
        task.id, action="submit_form", summary="Submit form", requested_by="hermes",
    )
    store.resolve_approval(approval.id, approved=True, resolved_by="user-1")
    assert store.get_task(task.id).status is TaskStatus.QUEUED
    with pytest.raises(ValueError, match="already been resolved"):
        store.resolve_approval(approval.id, approved=False, resolved_by="user-1")


def test_event_log_records_lifecycle(tmp_path):
    store = make_registry(tmp_path)
    task = make_task(store)
    store.transition(task.id, TaskStatus.RUNNING, actor_id="worker-1")
    store.transition(task.id, TaskStatus.COMPLETED, actor_id="worker-1")
    assert [event.event_type for event in store.events(task.id)] == [
        "created", "status_changed", "status_changed",
    ]
