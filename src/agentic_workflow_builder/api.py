"""FastAPI application — slice #1 endpoints: POST /workflows, GET /workflows/{id}.

Validation errors from validation.py are mapped to structured 400 responses.
The tool registry is not implemented yet (slice #2), so known_tools is always
an empty set — any tool_call step will reject with unknown_tool.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI path param resolution
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI needs runtime type

from agentic_workflow_builder.db import WorkflowRow, get_db
from agentic_workflow_builder.models import Step, Workflow
from agentic_workflow_builder.validation import WorkflowValidationError, validate_workflow

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

app = FastAPI(title="Agentic Workflow Builder", version="0.1.0")

# Slice #2 will inject a real tool registry here.
_KNOWN_TOOLS: set[str] = set()


def _row_to_workflow(row: WorkflowRow) -> Workflow:
    """Reconstruct a Workflow from its ORM row."""
    steps = [Step.model_validate(s) for s in row.steps]
    return Workflow(id=row.id, name=row.name, steps=steps)


@app.post("/workflows", status_code=201)
async def create_workflow(
    workflow: Workflow,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Workflow:
    """Persist a workflow after DAG validation.

    Returns 400 with a structured error body on any validation failure.
    Returns 201 with the stored Workflow (id included) on success.
    """
    try:
        validate_workflow(workflow, _KNOWN_TOOLS)
    except WorkflowValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"detail": exc.message, "error_type": exc.error_type},
        ) from exc

    row = WorkflowRow(
        id=workflow.id,
        name=workflow.name,
        steps=[step.model_dump(mode="json") for step in workflow.steps],
    )
    db.add(row)
    await db.flush()  # write to DB within the transaction; commit happens in get_db
    return _row_to_workflow(row)


@app.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Workflow:
    """Return a workflow by id, or 404 if not found."""
    row: WorkflowRow | None = await db.get(WorkflowRow, workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return _row_to_workflow(row)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Response:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
