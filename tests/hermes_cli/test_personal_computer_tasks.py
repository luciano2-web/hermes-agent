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
    assert store.events(task.id)[-1].event_type == "approval_resolved"


def test_approval_cannot_be_resolved_twice(tmp_path):
    store = make_registry(tmp_path)
    task = make_task(store)
    approval = store.request_approval(
        task.id, action="submit_form", summary="Submit form", requested_by="hermes",
    )
    store.resolve_approval(approval.id, approved=True, resolved_by="user-1")
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
