"""Passive message reactions, ported from the old JS bot's reactions.js.

The original was one static method per trigger, each re-lowercasing
msg.content and duplicating the same test-then-react/reply shape. Collapsed
here into two declarative rule tables + a single dispatch loop.

Two behavior fixes along the way:
- AHHMp4's and Kanye's source regexes had `^`/`$` binding to only one side of
  an `|` (e.g. `/^A|B$/` means `(^A)|(B$)`, not `^(A|B)$`) — likely a
  precedence slip, not intended looseness. Rewritten so the alternation is
  anchored as a whole.
- SemenJoke was gated on `silentGuildIds.includes(msg.silentGuildIds)` —
  `msg.silentGuildIds` doesn't exist, so that check was always false. This
  now honors `reaction_silent_guilds` like the plain reactions do.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

import discord
from discord.ext import commands


@dataclass(frozen=True)
class ReactRule:
    pattern: re.Pattern[str]
    emoji: str


@dataclass(frozen=True)
class EmojiSpamRule:
    """Fires only on messages that mention someone; replies with the message
    text plus a burst of randomly chosen emoji."""

    pattern: re.Pattern[str]
    emojis: tuple[str, ...]
    silenceable: bool = True


REACT_RULES: tuple[ReactRule, ...] = (
    ReactRule(re.compile(r"^yes.?$"), "<:yes:617874534137069569>"),
    ReactRule(re.compile(r"^no.?$"), "<:no:617874534149914624>"),
    ReactRule(re.compile(r"^(a{2,}h+|ah{2,})$"), "<a:aaaaahh:851947388294004786>"),
    ReactRule(re.compile(r"syes|kanye"), "<:kanye:590902214327795742>"),
)

EMOJI_SPAM_RULES: tuple[EmojiSpamRule, ...] = (
    EmojiSpamRule(
        re.compile(r"happy|hbd|bday|congrats|feliz"),
        ("🎉", "✨", "🥳", "🎈", "🎇", "🎊", "🎆"),
        silenceable=False,  # birthday wishes fire even in silenced guilds
    ),
    EmojiSpamRule(
        re.compile(r"^cum"),
        (
            "🍆", "💦", "😳", "💦", "👀",
            "<:ropes:1074411300807000074>", "<:ropes:1074411300807000074>",
        ),
    ),
)


class Reactions(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        content = message.content.lower()
        silenced = message.guild.id in self.bot.whitelist.reaction_silent_guilds

        if not silenced:
            for rule in REACT_RULES:
                if rule.pattern.search(content):
                    await message.add_reaction(rule.emoji)

        if not message.mentions:
            return

        for rule in EMOJI_SPAM_RULES:
            if silenced and rule.silenceable:
                continue
            if rule.pattern.search(content):
                spam = "".join(random.choices(rule.emojis, k=random.randint(100, 120)))
                await message.reply(f"***{message.content}!***\n{spam}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reactions(bot))
