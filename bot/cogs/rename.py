"""`/rename` — set another member's nickname. Ported from the old JS bot's
rename.js.

Two fixes from the original along the way: the self-rename check compared
`target.username === interaction.member.user.username` (a string that could
theoretically go stale); this compares IDs instead. And renaming could fail
silently (`.catch(() => {})`); this reports Discord's actual error back to
the caller instead of swallowing it.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

MAX_NICKNAME_LENGTH = 32
ERROR_COLOR = 15879747
SUCCESS_COLOR = 39129


class Rename(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="rename", description="Rename another user.")
    @app_commands.describe(target="The user to rename.", nickname="The nickname to apply.")
    @app_commands.default_permissions(manage_nicknames=True)
    async def rename(
        self, interaction: discord.Interaction, target: discord.Member, nickname: str
    ) -> None:
        if len(nickname) > MAX_NICKNAME_LENGTH:
            await interaction.response.send_message(
                embed=self._error_embed(
                    interaction,
                    target,
                    title="Error: Nickname too long.",
                    description=f"Can't update username, exceeds character limit of {MAX_NICKNAME_LENGTH}.",
                ),
                ephemeral=True,
            )
            return

        if target.id == interaction.user.id:
            await interaction.response.send_message(
                embed=self._error_embed(
                    interaction,
                    target,
                    title="Error: Can't nickname yourself!",
                    description="We don't do that here. Try renaming someone else instead.",
                ),
                ephemeral=True,
            )
            return

        old_name = target.nick or target.name
        try:
            await target.edit(nick=nickname, reason=f"Renamed by {interaction.user} via /rename")
        except discord.HTTPException as exc:
            await interaction.response.send_message(
                f"Couldn't rename {target.mention}: {exc.text or exc}",
                ephemeral=True,
            )
            return

        embed = discord.Embed(color=SUCCESS_COLOR)
        embed.set_author(
            name=f"{interaction.user.display_name} renamed {target.name}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="New Name", value=nickname, inline=True)
        embed.add_field(name="Old Name", value=old_name, inline=True)
        await interaction.response.send_message(embed=embed)

    @staticmethod
    def _error_embed(
        interaction: discord.Interaction,
        target: discord.Member,
        *,
        title: str,
        description: str,
    ) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=ERROR_COLOR)
        embed.set_author(
            name=f"{interaction.user.display_name}'s command failed.",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="If you think this is incorrect, bug Jaime.")
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Rename(bot))
