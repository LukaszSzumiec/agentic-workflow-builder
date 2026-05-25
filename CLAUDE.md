# agentic-workflow-builder

## Stack
- Python 3.13, uv for env/deps
- ruff (lint+format), mypy strict, pytest
- Docker for containerization

## Commands
- `make install` — sync deps via uv
- `make lint` / `make format` / `make type` / `make test`
- `make all` — full validation chain

## Conventions
- Type hints everywhere, mypy strict enforced (PEP 604 syntax: `str | None`)
- Tests in `tests/`, mirror the source layout in `src/`
- Source package lives under `src/agentic_workflow_builder/`
- No new dependencies without justification
