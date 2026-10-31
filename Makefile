# Developer entry points. Requires Docker, uv and Node.js 22+.
.DEFAULT_GOAL := help
COMPOSE := docker compose

# Reuse the database credentials from .env when it exists (same defaults as compose).
-include .env
PG_USER := $(or $(POSTGRES_USER),pmnews)
PG_PASSWORD := $(or $(POSTGRES_PASSWORD),pmnews-local)
PG_DB := $(or $(POSTGRES_DB),pmnews)

.PHONY: help setup up down logs seed reset-db dev test lint fmt typecheck check

help: ## Show this help
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python and Node dependencies, create .env, install git hooks
	@command -v docker >/dev/null || { echo "Docker is required: https://docs.docker.com/get-docker/"; exit 1; }
	@command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/ (brew install uv)"; exit 1; }
	@command -v npm >/dev/null || { echo "Node.js 22+ is required: https://nodejs.org/"; exit 1; }
	@test -f .env || { cp .env.example .env; echo "Created .env from .env.example"; }
	uv sync
	cd frontend && npm ci
	uv run pre-commit install

up: ## Build and start the stack (db, migrations, API, frontend) and wait until healthy
	$(COMPOSE) up --build --detach --wait

down: ## Stop the stack (data is kept)
	$(COMPOSE) down

logs: ## Follow logs of all services
	$(COMPOSE) logs --follow

seed: ## Load the thesis sample markets into the running stack
	$(COMPOSE) exec api python -m pmnews.db.seed

reset-db: ## Delete the local database volume and start again (destroys local data)
	$(COMPOSE) down --volumes

dev: ## Run the API on the host with auto-reload (needs `make up` for the database)
	DATABASE_URL=postgresql+asyncpg://$(PG_USER):$(PG_PASSWORD)@localhost:5432/$(PG_DB) \
		uv run uvicorn pmnews.api.app:app --reload --port 8000

test: ## Run the Python test suite (starts a throwaway Postgres container)
	uv run pytest

lint: ## Lint Python and frontend code
	uv run ruff check .
	uv run ruff format --check .
	cd frontend && npm run lint

fmt: ## Format Python code
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Type-check Python (mypy --strict) and TypeScript (tsc --noEmit)
	uv run mypy
	cd frontend && npm run typecheck

check: lint typecheck test ## Everything CI runs
