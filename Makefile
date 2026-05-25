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

# Infra targets — Postgres + Redis via docker-compose
.PHONY: infra-up infra-down infra-logs infra-reset

infra-up:
	docker compose up -d
	@echo "Waiting for services..."
	@docker compose ps

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

infra-reset:
	docker compose down -v
	docker compose up -d

# Frontend targets — delegate to frontend/Makefile
.PHONY: fe-dev fe-build fe-lint

fe-dev:
	$(MAKE) -C frontend dev

fe-build:
	$(MAKE) -C frontend build

fe-lint:
	$(MAKE) -C frontend lint
