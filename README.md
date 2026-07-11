# miku

Discord bot (discord.py, slash commands) with Postgres storage and read-only
visibility into the host's Docker containers.

## Architecture

Three containers, defined in [docker-compose.yml](docker-compose.yml):

- **bot** — the discord.py app. Talks to Postgres for storage and to the
  socket proxy for container info.
- **postgres** — Postgres 16 with a named volume for persistence.
- **docker-proxy** — [tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy).
  The host's Docker socket is mounted only here. The proxy allows read (GET)
  container endpoints plus restart/stop/kill (`ALLOW_RESTARTS=1`); all other
  writes are denied, so the bot can never create, remove, or exec into
  containers even if compromised.

### Restart safety model

The proxy cannot restrict restarts to specific containers (the Docker API
accepts IDs interchangeably with names, so path-based name filtering would be
bypassable). Instead, `/restart` is limited by two independent gates:

1. `GOD_USER` in `.env` — the one Discord user ID allowed to run `/restart`.
   Everyone else gets an ephemeral refusal (and no autocomplete suggestions).
   Left blank, `/restart` is disabled for everyone.
2. `restartable_containers` in `config/whitelist.yml` (see
   [config/whitelist.example.yml](config/whitelist.example.yml)) —
   regex patterns that must full-match the container name. **Temporarily**,
   an empty list means no name restriction; it will become mandatory later.
3. Discord permissions — `/restart` defaults to members with **Manage
   Server**, which hides it from everyone else's command picker. Discord
   can't hide commands per-user from bot code, but a server admin can
   manually restrict visibility to a single member under Server Settings →
   Integrations → miku → `/restart`. The `GOD_USER` check holds regardless.

## Setup

1. Create a bot in the [Discord Developer Portal](https://discord.com/developers/applications),
   copy its token, and invite it to your server with the `bot` and
   `applications.commands` scopes.
2. Configure secrets:
   ```sh
   cp .env.example .env
   # edit .env: set DISCORD_TOKEN and a real POSTGRES_PASSWORD
   ```
3. Configure the whitelist (gitignored, like `.env`):
   ```sh
   cp config/whitelist.example.yml config/whitelist.yml
   # edit it: your guild ID, optional channel IDs, restartable containers
   ```
   Slash commands are synced only to whitelisted guilds; non-whitelisted
   channels get a polite refusal.
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
| `/restart <name>` | Restart a container matching the restart whitelist (Manage Server by default) |
| `/stats` | Command usage counts for the server, from Postgres |

## Layout

- [bot/main.py](bot/main.py) — entrypoint, whitelist enforcement, guild command sync
- [bot/config.py](bot/config.py) — env settings and whitelist loading
- [bot/db.py](bot/db.py) — asyncpg pool, schema, queries
- [bot/docker_client.py](bot/docker_client.py) — read-only Docker status client
- [bot/cogs/](bot/cogs/) — slash command groups
