.PHONY: dev test e2e lint fmt install db-upgrade rta-install rta-test rta-lint

install:
	cd backend && uv sync
	cd frontend && npm install
	cd rta && uv sync

rta-install:
	cd rta && uv sync

dev:
	@mkdir -p data
	@trap 'kill 0' SIGINT SIGTERM EXIT; \
		(cd backend && uv run uvicorn poker_coach.main:app --reload --port 8000) & \
		(cd frontend && npm run dev) & \
		wait

test:
	cd backend && uv run pytest
	cd frontend && npm test
	cd rta && uv run pytest

rta-test:
	cd rta && uv run pytest

e2e:
	cd frontend && npm run e2e

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
	cd frontend && npm run lint && npm run typecheck
	cd rta && uv run ruff check . && uv run ruff format --check . && uv run mypy src

rta-lint:
	cd rta && uv run ruff check . && uv run ruff format --check . && uv run mypy src

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format
	cd rta && uv run ruff format . && uv run ruff check --fix .

db-upgrade:
	cd backend && uv run alembic upgrade head
