"""Unit tests for validation.py — pure function, no DB, no I/O.

Each test exercises one specific validation rule.
AAA pattern throughout.
"""

import pytest

from agentic_workflow_builder.models import LLMCallConfig, Step, ToolCallConfig, Workflow
from agentic_workflow_builder.validation import (
    CycleError,
    DuplicateStepIdError,
    EmptyWorkflowError,
    MissingDependencyError,
    UnknownToolError,
    validate_workflow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _llm_step(step_id: str, depends_on: list[str] | None = None) -> Step:
    return Step(
        id=step_id,
        type="llm_call",
        config=LLMCallConfig(system="sys", prompt="hello"),
        depends_on=depends_on or [],
    )


def _tool_step(step_id: str, tool_name: str, depends_on: list[str] | None = None) -> Step:
    return Step(
        id=step_id,
        type="tool_call",
        config=ToolCallConfig(tool_name=tool_name, args={}),
        depends_on=depends_on or [],
    )


def _workflow(*steps: Step) -> Workflow:
    return Workflow(name="test-workflow", steps=list(steps))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_accepts_valid_two_step_workflow() -> None:
    # Arrange
    wf = _workflow(_llm_step("a"), _llm_step("b", depends_on=["a"]))

    # Act / Assert — should not raise
    validate_workflow(wf, known_tools=set())


def test_accepts_single_step_workflow() -> None:
    wf = _workflow(_llm_step("a"))
    validate_workflow(wf, known_tools=set())


def test_accepts_tool_step_when_tool_is_known() -> None:
    wf = _workflow(_tool_step("t1", tool_name="search"))
    validate_workflow(wf, known_tools={"search"})


# ---------------------------------------------------------------------------
# Empty workflow
# ---------------------------------------------------------------------------


def test_rejects_empty_workflow() -> None:
    # Arrange
    wf = Workflow(name="empty", steps=[])

    # Act
    with pytest.raises(EmptyWorkflowError) as exc_info:
        validate_workflow(wf, known_tools=set())

    # Assert
    assert exc_info.value.error_type == "empty_workflow"


# ---------------------------------------------------------------------------
# Duplicate step ids
# ---------------------------------------------------------------------------


def test_rejects_duplicate_step_ids() -> None:
    wf = _workflow(_llm_step("a"), _llm_step("a"))

    with pytest.raises(DuplicateStepIdError) as exc_info:
        validate_workflow(wf, known_tools=set())

    assert exc_info.value.error_type == "duplicate_id"
    assert "a" in exc_info.value.message


def test_rejects_duplicate_id_even_with_different_types() -> None:
    wf = _workflow(_llm_step("shared"), _tool_step("shared", tool_name="x"))

    with pytest.raises(DuplicateStepIdError):
        validate_workflow(wf, known_tools={"x"})


# ---------------------------------------------------------------------------
# Missing dependency targets
# ---------------------------------------------------------------------------


def test_rejects_depends_on_pointing_at_nonexistent_step() -> None:
    # Step "b" depends on "ghost" which doesn't exist.
    wf = _workflow(_llm_step("a"), _llm_step("b", depends_on=["ghost"]))

    with pytest.raises(MissingDependencyError) as exc_info:
        validate_workflow(wf, known_tools=set())

    assert exc_info.value.error_type == "missing_dependency"
    assert "ghost" in exc_info.value.message


def test_rejects_self_dependency() -> None:
    # A step that depends on itself — missing dependency before cycle check
    wf = _workflow(_llm_step("a", depends_on=["a"]))

    # self-dependency creates both a missing_dependency (if we check before
    # building the graph) OR a cycle. Our implementation checks missing deps first.
    with pytest.raises((MissingDependencyError, CycleError)):
        validate_workflow(wf, known_tools=set())


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


def test_rejects_tool_call_with_unknown_tool_name() -> None:
    wf = _workflow(_tool_step("t1", tool_name="dangerous_tool"))

    with pytest.raises(UnknownToolError) as exc_info:
        validate_workflow(wf, known_tools=set())

    assert exc_info.value.error_type == "unknown_tool"
    assert "dangerous_tool" in exc_info.value.message


def test_accepts_tool_call_when_tool_is_in_known_tools() -> None:
    wf = _workflow(_tool_step("t1", tool_name="registered"))
    validate_workflow(wf, known_tools={"registered"})  # no exception


def test_rejects_only_unknown_tool_when_mixed() -> None:
    # One known tool, one unknown — should still fail.
    wf = _workflow(
        _tool_step("t1", tool_name="search"),
        _tool_step("t2", tool_name="mystery"),
    )

    with pytest.raises(UnknownToolError) as exc_info:
        validate_workflow(wf, known_tools={"search"})

    assert "mystery" in exc_info.value.message


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def test_rejects_cycle_when_two_steps_depend_on_each_other() -> None:
    # A → B and B → A forms a cycle.
    wf = _workflow(
        _llm_step("a", depends_on=["b"]),
        _llm_step("b", depends_on=["a"]),
    )

    with pytest.raises(CycleError) as exc_info:
        validate_workflow(wf, known_tools=set())

    assert exc_info.value.error_type == "cycle"


def test_rejects_three_node_cycle() -> None:
    wf = _workflow(
        _llm_step("a", depends_on=["c"]),
        _llm_step("b", depends_on=["a"]),
        _llm_step("c", depends_on=["b"]),
    )

    with pytest.raises(CycleError):
        validate_workflow(wf, known_tools=set())


def test_accepts_diamond_dag_without_cycle() -> None:
    # Diamond: a → b, a → c, b → d, c → d — valid DAG.
    wf = _workflow(
        _llm_step("a"),
        _llm_step("b", depends_on=["a"]),
        _llm_step("c", depends_on=["a"]),
        _llm_step("d", depends_on=["b", "c"]),
    )
    validate_workflow(wf, known_tools=set())  # no exception
