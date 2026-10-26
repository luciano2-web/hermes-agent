from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.platforms.api_server import APIServerAdapter
from gateway.config import PlatformConfig


def _request(*, key="computer-test-key", body=None, query=None, task_id=None):
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {key}"} if key else {}
    request.query = query or {}
    request.match_info = {"task_id": task_id} if task_id else {}
    request.json = AsyncMock(return_value=body or {})
    return request


@pytest.fixture
def adapter():
    return APIServerAdapter(PlatformConfig(enabled=True, extra={"key": "computer-test-key"}))


@pytest.mark.asyncio
async def test_computer_workspace_routes_are_advertised(adapter):
    routes = {(method, path) for method, path, _handler in adapter._http_route_table()}
    assert ("GET", "/api/computer/tasks") in routes
    assert ("POST", "/api/computer/tasks") in routes
    assert ("GET", "/api/computer/tasks/{task_id}") in routes
    assert ("POST", "/api/computer/tasks/{task_id}/transition") in routes
    assert ("POST", "/api/computer/tasks/{task_id}/events") in routes


@pytest.mark.asyncio
async def test_authenticated_api_creates_lists_and_transitions_task(adapter, monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    created = await adapter._handle_create_computer_task(_request(body={
        "channel": "desktop",
        "requester_id": "local-user",
        "title": "Open Chromium and inspect a page",
        "summary": "Use the existing desktop computer-use backend.",
        "request_key": "desktop:task:1",
        "metadata": {"requires_approval": True},
    }))
    assert created.status == 201
    task = json.loads(created.text)["task"]
    assert task["status"] == "queued"

    listed = await adapter._handle_list_computer_tasks(_request())
    assert [item["id"] for item in json.loads(listed.text)["tasks"]] == [task["id"]]

    transitioned = await adapter._handle_transition_computer_task(_request(
        body={"status": "running", "message": "Worker started"},
        task_id=task["id"],
    ))
    assert transitioned.status == 200
    assert json.loads(transitioned.text)["task"]["status"] == "running"


@pytest.mark.asyncio
async def test_computer_workspace_api_rejects_unauthenticated_requests(adapter):
    response = await adapter._handle_list_computer_tasks(_request(key="wrong"))
    assert response.status == 401


@pytest.mark.asyncio
async def test_computer_workspace_api_rejects_invalid_state_transition(adapter, monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    created = await adapter._handle_create_computer_task(_request(body={
        "channel": "desktop", "requester_id": "local-user", "title": "Check invoice"
    }))
    task_id = json.loads(created.text)["task"]["id"]

    response = await adapter._handle_transition_computer_task(_request(
        body={"status": "completed"}, task_id=task_id
    ))
    assert response.status == 400
    assert "cannot transition" in json.loads(response.text)["error"]
