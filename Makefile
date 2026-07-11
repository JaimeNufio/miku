.PHONY: up down build restart logs ps sync lock

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose restart bot

logs:
	docker compose logs -f bot

ps:
	docker compose ps

sync:
	uv sync

lock:
	uv lock
