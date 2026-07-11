"""Slash commands for read-only host container status."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.docker_client import ContainerStatus

STATUS_EMOJI = {
    "running": "🟢",
    "paused": "🟡",
    "restarting": "🟠",
    "exited": "🔴",
    "dead": "💀",
    "created": "⚪",
}


def _emoji(container: ContainerStatus) -> str:
    if container.health == "unhealthy":
        return "🤒"
    return STATUS_EMOJI.get(container.status, "❓")


class Containers(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="containers", description="List all Docker containers on the host")
    async def containers(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        statuses = await self.bot.docker.list_containers()
        if not statuses:
            await interaction.followup.send("No containers found.")
            return

        running = sum(1 for c in statuses if c.status == "running")
        embed = discord.Embed(
            title="Host containers",
            description=f"{running}/{len(statuses)} running",
            color=discord.Color.green() if running == len(statuses) else discord.Color.orange(),
        )
        lines = [f"{_emoji(c)} **{c.name}** — {c.state} · `{c.image}`" for c in statuses]
        # Field values cap at 1024 chars; chunk the list across fields.
        chunk: list[str] = []
        size = 0
        for line in lines:
            if size + len(line) + 1 > 1024:
                embed.add_field(name="​", value="\n".join(chunk), inline=False)
                chunk, size = [], 0
            chunk.append(line)
            size += len(line) + 1
        embed.add_field(name="​", value="\n".join(chunk), inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="container", description="Inspect one container's status")
    @app_commands.describe(name="Container name (as shown by /containers)")
    async def container(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer()
        status = await self.bot.docker.get_container(name)
        if status is None:
            await interaction.followup.send(f"No container named `{name}` found.", ephemeral=True)
            return

        embed = discord.Embed(title=f"{_emoji(status)} {status.name}", color=discord.Color.blurple())
        embed.add_field(name="Status", value=status.status)
        embed.add_field(name="Image", value=f"`{status.image}`")
        if status.health:
            embed.add_field(name="Health", value=status.health)
        await interaction.followup.send(embed=embed)

    @container.autocomplete("name")
    async def container_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            statuses = await self.bot.docker.list_containers()
        except Exception:  # noqa: BLE001 - autocomplete must never raise
            return []
        current = current.lower()
        return [
            app_commands.Choice(name=f"{_emoji(c)} {c.name}", value=c.name)
            for c in statuses
            if current in c.name.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Containers(bot))
