# miku

Discord bot (discord.py, slash commands) with Postgres storage and read-only
visibility into the host's Docker containers.

## Architecture

Four containers, defined in [docker-compose.yml](docker-compose.yml):

- **config-init** — one-shot; seeds `whitelist.yml` and `blacklist.yml` into
  the `configdata` named volume from the `.example.yml` files baked into the
  image, if they don't exist yet. `configdata` isn't a host bind mount — no
  path to configure in Portainer, and nothing depends on a host directory
  existing before first boot. Runs as root (the volume is root-owned until
  something writes to it); **bot** mounts the same volume read-only. This
  only seeds placeholder content — `whitelist.yml` still needs your real
  guild ID before slash commands will sync (see Setup below); the container
  won't crash-loop without that edit, but commands won't work in your
  server either until you do it. See `make push-whitelist` below for how to
  actually get an edit into the volume.
- **bot** — the discord.py app. Talks to Postgres for storage and to the
  socket proxy for container info.
- **postgres** — Postgres 16. Data dir defaults to a named volume (`pgdata`,
  Docker-managed); set `POSTGRES_DATA_DIR` to an absolute host path instead
  if you want it somewhere visible/backuppable (e.g. Portainer's
  Environment variables field: `POSTGRES_DATA_DIR=/mnt/data/miku/postgres`).
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
2. Configure secrets. `make up` creates `.env` from `.env.example`
   automatically if it's missing (see the Makefile section below), but you
   still need to edit it:
   ```sh
   # edit .env: set DISCORD_TOKEN and a real POSTGRES_PASSWORD
   ```
3. Configure the whitelist. `whitelist.yml`/`blacklist.yml` live in the
   `configdata` named volume, not a plain host file, so there's a local
   working copy (gitignored, like `.env`) you edit and then push in:
   ```sh
   cp config/whitelist.example.yml config/whitelist.yml   # (make push-whitelist does this too, if missing)
   # edit config/whitelist.yml: your guild ID, optional channel IDs, restartable containers
   make push-whitelist   # copies it into the running volume + restarts the bot
   ```
   Slash commands are synced only to whitelisted guilds; non-whitelisted
   channels get a polite refusal.
4. Optionally hide containers from `/containers`, `/container`, and
   `/restart` autocomplete the same way:
   ```sh
   cp config/blacklist.example.yml config/blacklist.yml   # (make push-blacklist does this too, if missing)
   # edit config/blacklist.yml: Docker labels ("key=value" or bare "key") to hide by
   make push-blacklist
   ```
   The seeded default (`excluded_labels: []`) hides nothing, so this step
   only matters if you want to change that. A container is dropped only if
   it carries one of these labels — labels are set at creation time, so
   this hides containers you've deliberately labeled going forward, not
   arbitrary pre-existing unlabeled ones.
5. Run:
   ```sh
   make up
   make logs
   ```

`config-init` seeds `whitelist.yml`/`blacklist.yml` into the volume with
placeholder content on first boot, so `make up` won't crash-loop even
before you've run `make push-whitelist` — but slash commands won't sync
anywhere real until you do.

## Makefile

| Target | Description |
| --- | --- |
| `make up` | Create `.env` from `.env.example` if missing, then build and start all containers in the background |
| `make down` | Stop and remove containers |
| `make build` | Build images without starting |
| `make restart` | Restart the bot container |
| `make cycle` | Full stop + rebuild + start (`down` then `up`) |
| `make logs` | Tail the bot's logs |
| `make ps` | Show container status |
| `make push-whitelist` | Copy local `config/whitelist.yml` into the `configdata` volume and restart the bot |
| `make push-blacklist` | Same, for `config/blacklist.yml` |
| `make sync` | Install/update local Python deps from `uv.lock` |
| `make lock` | Regenerate `uv.lock` after editing `pyproject.toml` |

Dependencies are managed with [uv](https://docs.astral.sh/uv/): edit
`pyproject.toml`, run `make lock`, and commit the updated `uv.lock`. The
Docker image installs from the lockfile directly, so no local Python
environment is required just to run the bot.

## Commands

| Command | Description |
| --- | --- |
| `/ping` | Gateway latency plus Postgres and Docker connectivity checks |
| `/containers` | List all host containers with status and image |
| `/container <name>` | Inspect one container (with name autocomplete) |
| `/restart <name>` | Restart a container matching the restart whitelist (Manage Server by default) |
| `/stats` | Command usage counts for the server, from Postgres |
| `/remind-me <duration> <message>` | Set a reminder (e.g. `2 days`, `3h`, `45 minutes`); persisted in Postgres, so it survives restarts. When it fires, a new message replies to the original confirmation, pinging you |
| `/rename <target> <nickname>` | Set another member's nickname (can't target yourself; Manage Nicknames by default) |

## Reactions

Passive, non-command message watching (requires the **Message Content**
privileged intent, enabled in the Discord Developer Portal under Bot):

| Trigger | Response |
| --- | --- |
| Message is exactly `yes`/`no` (+ one optional trailing char) | custom yes/no react |
| Message is a scream (`ahh`, `aaahhh`, ...) | animated react |
| Message contains `syes` or `kanye` | react |
| Message mentions someone and contains `happy`/`hbd`/`bday`/`congrats`/`feliz` | reply with the message text + a confetti burst |
| Message mentions someone and starts with `cum` | reply with the message text + an eggplant/water-drop burst |

`reaction_silent_guilds` in `whitelist.yml` mutes everything above except the
birthday reply for specific guilds.

## Layout

- [bot/main.py](bot/main.py) — entrypoint, whitelist enforcement, guild command sync
- [bot/config.py](bot/config.py) — env settings and whitelist loading
- [bot/db.py](bot/db.py) — asyncpg pool, schema, queries
- [bot/docker_client.py](bot/docker_client.py) — read-only Docker status client
- [bot/cogs/](bot/cogs/) — slash command groups and passive message reactions
