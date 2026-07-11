"""General-purpose slash commands: health checks and usage stats."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot import db


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot, database, and Docker connectivity")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            await self.bot.pool.fetchval("SELECT 1")
            db_status = "✅ connected"
        except Exception as exc:  # noqa: BLE001 - report any failure to the user
            db_status = f"❌ {type(exc).__name__}"

        try:
            await self.bot.docker.ping()
            docker_status = "✅ connected"
        except Exception as exc:  # noqa: BLE001
            docker_status = f"❌ {type(exc).__name__}"

        embed = discord.Embed(title="Pong! 🏓", color=discord.Color.green())
        embed.add_field(name="Gateway latency", value=f"{self.bot.latency * 1000:.0f} ms")
        embed.add_field(name="Postgres", value=db_status)
        embed.add_field(name="Docker", value=docker_status)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="Show slash command usage stats for this server")
    async def stats(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        rows = await db.command_stats(self.bot.pool, interaction.guild_id)
        if not rows:
            await interaction.followup.send("No commands logged yet.")
            return

        embed = discord.Embed(title="Command usage", color=discord.Color.blurple())
        for row in rows:
            embed.add_field(
                name=f"/{row['command']}",
                value=f"{row['uses']} uses · last {discord.utils.format_dt(row['last_used'], 'R')}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
