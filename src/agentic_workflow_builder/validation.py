"""Pure DAG validation for workflows.

No I/O, no DB — takes a Workflow and a known_tools set, raises typed
exceptions on any structural problem. Call from the API layer and inject
known_tools from the tool registry (empty set in slice #1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

if TYPE_CHECKING:
    from agentic_workflow_builder.models import Workflow


class WorkflowValidationError(Exception):
    """Base for all workflow validation failures."""

    error_type: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmptyWorkflowError(WorkflowValidationError):
    error_type = "empty_workflow"


class DuplicateStepIdError(WorkflowValidationError):
    error_type = "duplicate_id"


class MissingDependencyError(WorkflowValidationError):
    error_type = "missing_dependency"


class CycleError(WorkflowValidationError):
    error_type = "cycle"


class UnknownToolError(WorkflowValidationError):
    error_type = "unknown_tool"


def validate_workflow(workflow: Workflow, known_tools: set[str]) -> None:
    """Raise a WorkflowValidationError subclass on any DAG problem.

    Checks, in order:
      1. Not empty
      2. No duplicate step ids
      3. All depends_on targets exist
      4. All tool_call steps reference a known tool
      5. No cycles in the dependency graph
    """
    from agentic_workflow_builder.models import ToolCallConfig

    if not workflow.steps:
        raise EmptyWorkflowError("Workflow must contain at least one step.")

    step_ids = [step.id for step in workflow.steps]

    # Detect duplicates before building any set — preserves the first duplicate for the message.
    seen: set[str] = set()
    for sid in step_ids:
        if sid in seen:
            raise DuplicateStepIdError(f"Duplicate step id: '{sid}'.")
        seen.add(sid)

    id_set = seen  # reuse — all unique at this point

    for step in workflow.steps:
        for dep in step.depends_on:
            if dep not in id_set:
                raise MissingDependencyError(
                    f"Step '{step.id}' depends on unknown step '{dep}'."
                )

    for step in workflow.steps:
        if step.type == "tool_call" and isinstance(step.config, ToolCallConfig):
            tool_name = step.config.tool_name
            if tool_name not in known_tools:
                raise UnknownToolError(f"Unknown tool '{tool_name}'.")

    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_nodes_from(step_ids)
    for step in workflow.steps:
        for dep in step.depends_on:
            graph.add_edge(dep, step.id)

    if not nx.is_directed_acyclic_graph(graph):
        cycle_edges = nx.find_cycle(graph)
        cycle_nodes = " → ".join(u for u, _ in cycle_edges)
        raise CycleError(f"Cycle detected: {cycle_nodes}.")
