"""Entrypoint: wires settings, Postgres, Docker monitor, and slash commands."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot.config import Blacklist, Settings, Whitelist
from bot.docker_client import DockerMonitor

log = logging.getLogger("miku")

COGS = ("bot.cogs.general", "bot.cogs.containers", "bot.cogs.reactions", "bot.cogs.reminders")


class WhitelistedTree(app_commands.CommandTree):
    """Rejects any interaction outside the configured guild/channel whitelist."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        whitelist: Whitelist = interaction.client.whitelist
        if whitelist.allows(interaction.guild_id, interaction.channel_id):
            return True
        if interaction.type is discord.InteractionType.application_command:
            await interaction.response.send_message(
                "This channel isn't whitelisted for bot commands.", ephemeral=True
            )
        return False


class MikuBot(commands.Bot):
    pool: object  # asyncpg.Pool, set in setup_hook
    docker: DockerMonitor

    def __init__(self, settings: Settings, whitelist: Whitelist, blacklist: Blacklist) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # required to read content for reactions.py
        super().__init__(
            command_prefix=commands.when_mentioned,  # unused; slash commands only
            intents=intents,
            tree_cls=WhitelistedTree,
        )
        self.settings = settings
        self.whitelist = whitelist
        self.blacklist = blacklist

    async def setup_hook(self) -> None:
        self.pool = await db.create_pool(self.settings.database_url)
        self.docker = DockerMonitor(self.settings.docker_host, blacklist=self.blacklist)

        for cog in COGS:
            await self.load_extension(cog)

        # Sync commands per whitelisted guild: instant availability, and the
        # commands simply don't exist anywhere else.
        for guild_id in self.whitelist.guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d commands to guild %d", len(synced), guild_id)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id %d)", self.user, self.user.id)

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command | app_commands.ContextMenu,
    ) -> None:
        try:
            await db.log_command(
                self.pool,
                interaction.guild_id,
                interaction.channel_id,
                interaction.user.id,
                command.qualified_name,
            )
        except Exception:  # noqa: BLE001 - logging must not break command flow
            log.exception("Failed to log command usage")

    async def close(self) -> None:
        await super().close()
        if hasattr(self, "pool"):
            await self.pool.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    whitelist = Whitelist.load(settings.whitelist_path)
    blacklist = Blacklist.load(settings.blacklist_path)
    log.info("Whitelist: %d guild(s)", len(whitelist.guild_ids))
    log.info("Blacklist: %d label(s)", len(blacklist.labels))

    bot = MikuBot(settings, whitelist, blacklist)
    bot.run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
