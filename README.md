# miku

Discord bot (discord.py, slash commands) with Postgres storage and read-only
visibility into the host's Docker containers.

## Architecture

Three containers, defined in [docker-compose.yml](docker-compose.yml):

- **bot** — the discord.py app. Talks to Postgres for storage and to the
  socket proxy for container info.
- **postgres** — Postgres 16 with a named volume for persistence.
- **docker-proxy** — [tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy).
  The host's Docker socket is mounted only here, and the proxy allows only
  read (GET) container endpoints. The bot can list/inspect containers but can
  never start, stop, or remove anything, even if compromised.

## Setup

1. Create a bot in the [Discord Developer Portal](https://discord.com/developers/applications),
   copy its token, and invite it to your server with the `bot` and
   `applications.commands` scopes.
2. Configure secrets:
   ```sh
   cp .env.example .env
   # edit .env: set DISCORD_TOKEN and a real POSTGRES_PASSWORD
   ```
3. Configure the whitelist in [config/whitelist.yml](config/whitelist.yml)
   with your guild ID (and optionally channel IDs). Slash commands are synced
   only to whitelisted guilds; non-whitelisted channels get a polite refusal.
4. Run:
   ```sh
   docker compose up --build -d
   docker compose logs -f bot
   ```

The whitelist is mounted read-only into the container; after editing it,
`docker compose restart bot` picks up changes.

## Commands

| Command | Description |
| --- | --- |
| `/ping` | Gateway latency plus Postgres and Docker connectivity checks |
| `/containers` | List all host containers with status and image |
| `/container <name>` | Inspect one container (with name autocomplete) |
| `/stats` | Command usage counts for the server, from Postgres |

## Layout

- [bot/main.py](bot/main.py) — entrypoint, whitelist enforcement, guild command sync
- [bot/config.py](bot/config.py) — env settings and whitelist loading
- [bot/db.py](bot/db.py) — asyncpg pool, schema, queries
- [bot/docker_client.py](bot/docker_client.py) — read-only Docker status client
- [bot/cogs/](bot/cogs/) — slash command groups
