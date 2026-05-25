"""Integration tests for POST /workflows and GET /workflows/{id}.

Each test uses a real Postgres instance (via testcontainers) and rolls back
after completion. Tests exercise both happy path and all validation failure modes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _two_step_payload() -> dict[str, Any]:
    return {
        "name": "my-workflow",
        "steps": [
            {
                "id": "step-a",
                "type": "llm_call",
                "config": {
                    "system": "You are helpful.",
                    "prompt": "Summarise {{inputs.text}}",
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 512,
                },
                "depends_on": [],
                "timeout_seconds": 60,
            },
            {
                "id": "step-b",
                "type": "llm_call",
                "config": {
                    "system": "You are concise.",
                    "prompt": "Translate {{steps.step-a.result}}",
                },
                "depends_on": ["step-a"],
                "timeout_seconds": 120,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_valid_workflow_returns_201_with_workflow(client: AsyncClient) -> None:
    # Arrange
    payload = _two_step_payload()

    # Act
    response = await client.post("/workflows", json=payload)

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "my-workflow"
    assert len(body["steps"]) == 2
    assert body["steps"][0]["id"] == "step-a"
    assert body["steps"][1]["id"] == "step-b"
    assert "id" in body  # server-assigned UUID


@pytest.mark.asyncio
async def test_get_workflow_by_id_returns_200_with_deep_equal_payload(
    client: AsyncClient,
) -> None:
    # Arrange — post a workflow, capture its id
    payload = _two_step_payload()
    post_response = await client.post("/workflows", json=payload)
    assert post_response.status_code == 201
    workflow_id = post_response.json()["id"]

    # Act
    get_response = await client.get(f"/workflows/{workflow_id}")

    # Assert
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == workflow_id
    assert body["name"] == "my-workflow"
    assert body["steps"] == post_response.json()["steps"]


@pytest.mark.asyncio
async def test_server_generates_id_when_none_provided(client: AsyncClient) -> None:
    # Arrange — no `id` field in payload; server must generate one
    payload = _two_step_payload()

    # Act
    response = await client.post("/workflows", json=payload)

    # Assert
    assert response.status_code == 201
    workflow_id = response.json().get("id")
    assert workflow_id is not None
    uuid.UUID(workflow_id)  # raises ValueError if not a valid UUID


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unknown_workflow_id_returns_404(client: AsyncClient) -> None:
    # Arrange — a UUID that was never stored
    missing_id = str(uuid.uuid4())

    # Act
    response = await client.get(f"/workflows/{missing_id}")

    # Assert
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Validation failures — all expect 400 with structured error_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_workflow_with_cycle_returns_400_cycle(client: AsyncClient) -> None:
    # Arrange — A→B and B→A
    payload: dict[str, Any] = {
        "name": "cyclic",
        "steps": [
            {
                "id": "a",
                "type": "llm_call",
                "config": {"system": "s", "prompt": "p"},
                "depends_on": ["b"],
            },
            {
                "id": "b",
                "type": "llm_call",
                "config": {"system": "s", "prompt": "p"},
                "depends_on": ["a"],
            },
        ],
    }

    # Act
    response = await client.post("/workflows", json=payload)

    # Assert
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_type"] == "cycle"


@pytest.mark.asyncio
async def test_post_workflow_with_duplicate_step_ids_returns_400_duplicate_id(
    client: AsyncClient,
) -> None:
    payload: dict[str, Any] = {
        "name": "dupe",
        "steps": [
            {
                "id": "same",
                "type": "llm_call",
                "config": {"system": "s", "prompt": "p"},
                "depends_on": [],
            },
            {
                "id": "same",
                "type": "llm_call",
                "config": {"system": "s", "prompt": "p"},
                "depends_on": [],
            },
        ],
    }

    response = await client.post("/workflows", json=payload)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_type"] == "duplicate_id"


@pytest.mark.asyncio
async def test_post_workflow_with_missing_depends_on_target_returns_400_missing_dependency(
    client: AsyncClient,
) -> None:
    payload: dict[str, Any] = {
        "name": "missing-dep",
        "steps": [
            {
                "id": "a",
                "type": "llm_call",
                "config": {"system": "s", "prompt": "p"},
                "depends_on": ["ghost"],
            },
        ],
    }

    response = await client.post("/workflows", json=payload)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_type"] == "missing_dependency"


@pytest.mark.asyncio
async def test_post_workflow_with_unknown_tool_returns_400_unknown_tool(
    client: AsyncClient,
) -> None:
    payload: dict[str, Any] = {
        "name": "bad-tool",
        "steps": [
            {
                "id": "t1",
                "type": "tool_call",
                "config": {"tool_name": "nonexistent_tool", "args": {}},
                "depends_on": [],
            },
        ],
    }

    response = await client.post("/workflows", json=payload)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_type"] == "unknown_tool"


@pytest.mark.asyncio
async def test_post_empty_workflow_returns_400_empty_workflow(client: AsyncClient) -> None:
    payload: dict[str, Any] = {"name": "empty", "steps": []}

    response = await client.post("/workflows", json=payload)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_type"] == "empty_workflow"
