.PHONY: install lint format type test all clean

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

type:
	uv run mypy .

test:
	uv run pytest -v

all: lint type test

clean:
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
