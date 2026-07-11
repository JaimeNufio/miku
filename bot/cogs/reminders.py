"""`/remind-me` and the background loop that delivers due reminders.

Reminders are rows in Postgres (remind_at timestamp), not in-memory asyncio
timers, so they survive bot restarts: the loop just asks "what's overdue?"
on every tick. A reminder due while the bot happens to be down fires late,
on the next tick after it's back — never lost.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot import db

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30

_UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800,
}
_DURATION_RE = re.compile(
    r"^\s*(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w)\s*$",
    re.IGNORECASE,
)


def parse_duration(text: str) -> timedelta | None:
    match = _DURATION_RE.match(text)
    if not match:
        return None
    amount, unit = match.groups()
    return timedelta(seconds=int(amount) * _UNIT_SECONDS[unit.lower()])


class Reminders(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self) -> None:
        self.check_reminders.cancel()

    @app_commands.command(name="remind-me", description="Set a reminder")
    @app_commands.describe(
        duration="e.g. '2 days', '3h', '45 minutes'",
        message="What to remind you about",
    )
    async def remind_me(
        self, interaction: discord.Interaction, duration: str, message: str
    ) -> None:
        delta = parse_duration(duration)
        if delta is None:
            await interaction.response.send_message(
                "Couldn't parse that duration — try something like `2 days`, `3h`, or `45 minutes`.",
                ephemeral=True,
            )
            return

        remind_at = discord.utils.utcnow() + delta
        # Not ephemeral: the interaction token needed to reply to an ephemeral
        # response expires in 15 minutes, long before most reminders fire.
        # A real channel message can be referenced by ID indefinitely.
        await interaction.response.send_message(
            f"Got it - I'll remind you at {discord.utils.format_dt(remind_at)}"
        )
        sent = await interaction.original_response()
        await db.create_reminder(
            self.bot.pool,
            interaction.guild_id,
            interaction.channel_id,
            sent.id,
            interaction.user.id,
            message,
            remind_at,
        )

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def check_reminders(self) -> None:
        for row in await db.due_reminders(self.bot.pool):
            channel = self.bot.get_channel(row["channel_id"])
            if channel is not None:
                reference = discord.MessageReference(
                    message_id=row["message_id"],
                    channel_id=row["channel_id"],
                    fail_if_not_exists=False,
                )
                try:
                    await channel.send(
                        f"⏰ <@{row['user_id']}> - {row['message']}", reference=reference
                    )
                except discord.HTTPException:
                    log.exception("Failed to deliver reminder %d", row["id"])
            await db.delete_reminder(self.bot.pool, row["id"])

    @check_reminders.before_loop
    async def before_check_reminders(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reminders(bot))
