.PHONY: up down build restart cycle logs ps sync lock push-whitelist push-blacklist

up: .env
	docker compose up --build -d

.env:
	cp .env.example .env
	@echo "Created .env from .env.example — fill in real secrets before this matters."

config/whitelist.yml:
	cp config/whitelist.example.yml config/whitelist.yml

config/blacklist.yml:
	cp config/blacklist.example.yml config/blacklist.yml

# whitelist.yml/blacklist.yml live in the configdata named volume, not a
# bind-mounted host path, so editing the local copy does nothing on its own.
# These push it into the volume via the config-init container (the one with
# read-write access) and restart the bot to pick it up.
push-whitelist: config/whitelist.yml
	docker cp config/whitelist.yml miku-config-init:/app/config/whitelist.yml
	docker compose restart bot

push-blacklist: config/blacklist.yml
	docker cp config/blacklist.yml miku-config-init:/app/config/blacklist.yml
	docker compose restart bot

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
