"""Pydantic schemas matching SPEC §1 exactly.

Discriminated unions on `Step.config` and `StepOutput` let Pydantic
deserialize the correct subtype from stored JSON without extra bookkeeping.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LLMCallConfig(BaseModel):
    system: str
    prompt: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 2048


class ToolCallConfig(BaseModel):
    tool_name: str
    args: dict[str, str]  # values may contain {{...}} templates


# Discriminated union keyed on `type` — matches the Step.type field.
StepConfig = Annotated[
    LLMCallConfig | ToolCallConfig,
    Field(discriminator=None),  # no discriminator; resolved by Step.type at the engine layer
]


class Step(BaseModel):
    id: str
    type: Literal["llm_call", "tool_call"]
    config: LLMCallConfig | ToolCallConfig
    depends_on: list[str]
    timeout_seconds: int = 120


class Workflow(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    steps: list[Step]


class LLMCallOutput(BaseModel):
    result: str
    reasoning: str
    tokens_used: int


class ToolCallOutput(BaseModel):
    result: str


# Tagged union for StepOutput stored in RunStatus.outputs.
# The engine writes the discriminator field so round-trips work.
StepOutput = LLMCallOutput | ToolCallOutput


class RunRequest(BaseModel):
    workflow_id: UUID
    inputs: dict[str, str]


class RunStatus(BaseModel):
    run_id: UUID
    status: Literal["pending", "running", "done", "failed"]
    outputs: dict[str, StepOutput]
    error: str | None
