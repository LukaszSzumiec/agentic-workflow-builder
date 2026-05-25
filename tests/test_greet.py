from agentic_workflow_builder import greet


def test_greet_returns_formatted_string() -> None:
    assert greet("world") == "Hello, world"


def test_greet_with_empty_string() -> None:
    # Unhappy path: empty name produces a valid (if odd) greeting rather than crashing.
    assert greet("") == "Hello, "
