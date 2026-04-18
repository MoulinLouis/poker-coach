.PHONY: dev test lint fmt install db-upgrade

install:
	cd backend && uv sync
	cd frontend && npm install

dev:
	@mkdir -p data
	@trap 'kill 0' SIGINT SIGTERM EXIT; \
		(cd backend && uv run uvicorn poker_coach.main:app --reload --port 8000) & \
		(cd frontend && npm run dev) & \
		wait

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
	cd frontend && npm run lint && npm run typecheck

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

db-upgrade:
	cd backend && uv run alembic upgrade head
