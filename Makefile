# Koya Content Agent — dev convenience commands.
# Run `make help` (or just `make`) to list everything below.
#
# Services in this project:
#   api      — FastAPI orchestrator (backend/app)
#   worker   — polling worker that drives the pipeline (backend/worker)
#   frontend — Next.js app (backend-first build; not scaffolded yet)
#
# `make dev` runs every service that currently exists, concurrently.
# To run only some of them, either call their target directly:
#     make api
#     make worker
# or override SERVICES on `make dev`:
#     make dev SERVICES="api worker"

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DEFAULT_GOAL := help

BACKEND_DIR  := backend
FRONTEND_DIR := frontend

# Paths from the repo root — used for bootstrapping the venv itself.
VENV := $(BACKEND_DIR)/.venv
PIP  := $(VENV)/bin/pip

# Paths relative to $(BACKEND_DIR) — used in recipes that `cd` there first,
# so backend/ code sees the cwd it expects (pydantic-settings' `.env`
# loading and `python -m` module resolution both assume cwd == backend/).
VENV_BIN := .venv/bin
PY       := $(VENV_BIN)/python
UVICORN  := $(VENV_BIN)/uvicorn
ALEMBIC  := $(VENV_BIN)/alembic
PYTEST   := $(VENV_BIN)/pytest
RUFF     := $(VENV_BIN)/ruff

API_HOST ?= 0.0.0.0
API_PORT ?= 8000

# Which services `make dev` brings up. Override to run a subset, e.g.:
#   make dev SERVICES="api worker"
SERVICES ?= api worker frontend

# `make migration m="add x"` / `make wipe id=<uuid>` / `make stage-events id=<uuid>`
m  ?= auto
id ?=

.PHONY: help \
	install backend-install frontend-install check-env \
	dev api api-dev worker worker-dev frontend frontend-dev \
	test backend-test frontend-test \
	lint backend-lint frontend-lint \
	migration migrate migrate-up migrate-down migrate-history migrate-current \
	seed wipe stage-events \
	backend-shell clean

help: ## Show this help
	@echo "Koya Content Agent — available commands:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## ---------------------------------------------------------------------------
## Install
## ---------------------------------------------------------------------------

install: backend-install frontend-install ## Install backend (+ frontend, if scaffolded) dependencies

backend-install: ## Install backend Python dependencies into backend/.venv (editable, with dev extras)
	if [ ! -d "$(VENV)" ]; then \
		echo "Creating venv at $(VENV)..."; \
		python3 -m venv $(VENV); \
	fi
	$(PIP) install --upgrade pip -q
	cd $(BACKEND_DIR) && $(VENV_BIN)/pip install -e ".[dev]" -q

frontend-install: ## Install frontend dependencies (npm install) — no-op until frontend/ exists
	if [ -d "$(FRONTEND_DIR)" ]; then \
		cd $(FRONTEND_DIR) && npm install; \
	else \
		echo "frontend/ not scaffolded yet — skipping frontend-install"; \
	fi

check-env: ## Verify backend/.env exists (fails fast with a clear message otherwise)
	if [ ! -f "$(BACKEND_DIR)/.env" ]; then \
		echo "Missing $(BACKEND_DIR)/.env — copy it from $(BACKEND_DIR)/.env.example and fill in real values:"; \
		echo "  cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env"; \
		exit 1; \
	fi

## ---------------------------------------------------------------------------
## Run
## ---------------------------------------------------------------------------

dev: check-env ## Run api + worker + frontend concurrently (Ctrl+C stops all). Override: make dev SERVICES="api worker"
	# `kill 0` alone isn't enough here: uvicorn's --reload mode spawns its
	# actual server via multiprocessing "spawn", which re-execs with a
	# generic bootstrap command line — it doesn't contain "uvicorn" or
	# "app.main:app" at all, so a `pkill -f` on that pattern misses it too.
	# It's left running, orphaned, still holding the port. The one thing
	# that reliably identifies it is the port it's bound to, so that's the
	# real cleanup key; kill-by-group and kill-by-pattern are kept as
	# defense in depth for the worker and any non-reload process.
	trap 'kill 0 2>/dev/null || true; \
		fuser -k $(API_PORT)/tcp 2>/dev/null || true; \
		pkill -f "uvicorn app.main:app" 2>/dev/null || true; \
		pkill -f "worker.main" 2>/dev/null || true; \
		true' EXIT INT TERM
	for s in $(SERVICES); do \
		case "$$s" in \
			api)      $(MAKE) --no-print-directory api-dev & ;; \
			worker)   $(MAKE) --no-print-directory worker-dev & ;; \
			frontend) $(MAKE) --no-print-directory frontend-dev & ;; \
			*) echo "unknown service '$$s' (expected: api, worker, frontend)"; exit 1 ;; \
		esac; \
	done
	wait

api: api-dev ## Run only the FastAPI dev server (alias for api-dev)

api-dev: check-env ## Run the FastAPI dev server with autoreload (default 0.0.0.0:8000, override API_HOST/API_PORT)
	cd $(BACKEND_DIR) && $(UVICORN) app.main:app --reload --host $(API_HOST) --port $(API_PORT)

worker: worker-dev ## Run only the polling worker (alias for worker-dev)

worker-dev: check-env ## Run the polling worker (claims jobs, executes pipeline steps, retries/dead-letters)
	cd $(BACKEND_DIR) && PYTHONUNBUFFERED=1 $(PY) -m worker.main

frontend: frontend-dev ## Run only the frontend dev server (alias for frontend-dev)

frontend-dev: ## Run the Next.js dev server — no-op with a message until frontend/ exists
	if [ -d "$(FRONTEND_DIR)" ]; then \
		cd $(FRONTEND_DIR) && npm run dev; \
	else \
		echo "frontend/ not scaffolded yet — nothing to run. (backend-first build order, see docs/work/BUILD_LOG.md)"; \
	fi

## ---------------------------------------------------------------------------
## Test & lint
## ---------------------------------------------------------------------------

test: backend-test ## Run all backend tests (pytest -q)

backend-test: ## Run backend tests
	cd $(BACKEND_DIR) && $(PYTEST) -q

frontend-test: ## Run frontend tests — no-op until frontend/ exists
	if [ -d "$(FRONTEND_DIR)" ]; then \
		cd $(FRONTEND_DIR) && npm test; \
	else \
		echo "frontend/ not scaffolded yet — nothing to test"; \
	fi

lint: backend-lint frontend-lint ## Run backend (ruff) + frontend (eslint) lint

backend-lint: ## Run ruff over the backend
	cd $(BACKEND_DIR) && $(RUFF) check .

frontend-lint: ## Run eslint on frontend — no-op until frontend/ exists
	if [ -d "$(FRONTEND_DIR)" ]; then \
		cd $(FRONTEND_DIR) && npm run lint; \
	else \
		echo "frontend/ not scaffolded yet — nothing to lint"; \
	fi

## ---------------------------------------------------------------------------
## Database & migrations (Alembic, against the Supabase project in backend/.env)
## ---------------------------------------------------------------------------

migration: check-env ## Add a new blank Alembic migration — usage: make migration m="add x"
	cd $(BACKEND_DIR) && $(ALEMBIC) revision -m "$(m)"

migrate: migrate-up ## Alias for migrate-up

migrate-up: check-env ## Apply all pending migrations (alembic upgrade head)
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head

migrate-down: check-env ## Roll back the last migration (alembic downgrade -1)
	cd $(BACKEND_DIR) && $(ALEMBIC) downgrade -1

migrate-history: check-env ## Show migration history
	cd $(BACKEND_DIR) && $(ALEMBIC) history --verbose

migrate-current: check-env ## Show the current migration revision
	cd $(BACKEND_DIR) && $(ALEMBIC) current

## ---------------------------------------------------------------------------
## Seed / inspect data (backend/scripts/, see architecture.md §9.2)
## ---------------------------------------------------------------------------

seed: check-env ## Seed the example content request trace (architecture.md §8) end to end
	cd $(BACKEND_DIR) && $(PY) -m scripts.seed_example_data

wipe: check-env ## Cascade-delete one content request — usage: make wipe id=<content_request_id>
	if [ -z "$(id)" ]; then echo "usage: make wipe id=<content_request_id>"; exit 1; fi
	cd $(BACKEND_DIR) && $(PY) -m scripts.wipe_request $(id)

stage-events: check-env ## Print the stage_events trail for one request — usage: make stage-events id=<content_request_id>
	if [ -z "$(id)" ]; then echo "usage: make stage-events id=<content_request_id>"; exit 1; fi
	cd $(BACKEND_DIR) && $(PY) -m scripts.print_stage_events $(id)

## ---------------------------------------------------------------------------
## Misc
## ---------------------------------------------------------------------------

backend-shell: ## Drop into a shell with the backend venv activated
	cd $(BACKEND_DIR) && exec bash --rcfile <(echo "source .venv/bin/activate")

clean: ## Remove Python/pytest/ruff caches
	find $(BACKEND_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache
