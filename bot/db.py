"""Postgres access via an asyncpg pool, plus startup schema creation."""

from __future__ import annotations

import asyncio
import datetime
import logging

import asyncpg

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS command_log (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    channel_id  BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    command     TEXT   NOT NULL,
    invoked_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS command_log_command_idx ON command_log (command);

CREATE TABLE IF NOT EXISTS reminders (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    channel_id  BIGINT NOT NULL,
    message_id  BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    message     TEXT NOT NULL,
    remind_at   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS message_id BIGINT;
CREATE INDEX IF NOT EXISTS reminders_remind_at_idx ON reminders (remind_at);
"""


async def create_pool(database_url: str, *, retries: int = 10, delay: float = 3.0) -> asyncpg.Pool:
    """Connect to Postgres, retrying while the container finishes starting."""
    for attempt in range(1, retries + 1):
        try:
            pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        except (OSError, asyncpg.PostgresError) as exc:
            if attempt == retries:
                raise
            log.warning("Postgres not ready (attempt %d/%d): %s", attempt, retries, exc)
            await asyncio.sleep(delay)
        else:
            async with pool.acquire() as conn:
                await conn.execute(SCHEMA)
            log.info("Connected to Postgres and ensured schema")
            return pool
    raise RuntimeError("unreachable")


async def log_command(
    pool: asyncpg.Pool, guild_id: int, channel_id: int, user_id: int, command: str
) -> None:
    await pool.execute(
        "INSERT INTO command_log (guild_id, channel_id, user_id, command) VALUES ($1, $2, $3, $4)",
        guild_id,
        channel_id,
        user_id,
        command,
    )


async def command_stats(pool: asyncpg.Pool, guild_id: int, limit: int = 10) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT command, count(*) AS uses, max(invoked_at) AS last_used
        FROM command_log
        WHERE guild_id = $1
        GROUP BY command
        ORDER BY uses DESC
        LIMIT $2
        """,
        guild_id,
        limit,
    )


async def create_reminder(
    pool: asyncpg.Pool,
    guild_id: int,
    channel_id: int,
    message_id: int,
    user_id: int,
    message: str,
    remind_at: datetime.datetime,
) -> int:
    return await pool.fetchval(
        """
        INSERT INTO reminders (guild_id, channel_id, message_id, user_id, message, remind_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        guild_id,
        channel_id,
        message_id,
        user_id,
        message,
        remind_at,
    )


async def due_reminders(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch(
        "SELECT id, channel_id, message_id, user_id, message FROM reminders WHERE remind_at <= now()"
    )


async def delete_reminder(pool: asyncpg.Pool, reminder_id: int) -> None:
    await pool.execute("DELETE FROM reminders WHERE id = $1", reminder_id)
