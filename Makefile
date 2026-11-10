.PHONY: help up down logs migrate makemigrations test lint typecheck

help:
	@echo "up | down | logs | migrate | makemigrations | test | lint | typecheck"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

test:
	docker compose exec backend pytest

lint:
	docker compose exec backend ruff check .
	docker compose exec backend ruff format --check .

typecheck:
	docker compose exec storefront pnpm typecheck
	docker compose exec seller-portal pnpm typecheck