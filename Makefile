.PHONY: install migrate run test lint format docker-up docker-down logs backup

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

migrate:
	.venv/bin/alembic upgrade head

run:
	.venv/bin/python -m app.main

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check app tests migrations

format:
	.venv/bin/ruff format app tests migrations
	.venv/bin/ruff check app tests migrations --fix

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

logs:
	docker compose logs -f --tail=200

backup:
	.venv/bin/python -m app.tools.backup
