.PHONY: install dev build typecheck lint format check all clean

install:
	pnpm install

dev:
	pnpm dev

build:
	pnpm build

typecheck:
	pnpm typecheck

lint:
	pnpm lint

format:
	pnpm format

check: typecheck lint
	pnpm format:check

all: check build

clean:
	rm -rf node_modules dist .vite
