.PHONY: up down build restart cycle logs ps sync lock

up: .env
	docker compose up --build -d

.env:
	cp .env.example .env
	@echo "Created .env from .env.example — fill in real secrets before this matters."

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose restart bot

cycle:
	docker compose down
	docker compose up --build -d

logs:
	docker compose logs -f bot

ps:
	docker compose ps

sync:
	uv sync

lock:
	uv lock
