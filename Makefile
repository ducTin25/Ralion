.PHONY: run test test-docker lint format typecheck check ci-local clean db-up migrate migrate-check migrate-new

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

test-docker:
	powershell -ExecutionPolicy Bypass -File scripts/test-backend.ps1

db-up:
	docker compose up -d db

migrate:
	python -m alembic upgrade head

migrate-check:
	python -m alembic check

migrate-new:
	python -m alembic revision --autogenerate -m "$(msg)"

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint format test

ci-local:
	powershell -ExecutionPolicy Bypass -File scripts/ci.ps1

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
