"""Settings from environment variables and the guild/channel whitelist file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    token: str
    database_url: str
    docker_host: str
    whitelist_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            token = os.environ["DISCORD_TOKEN"]
            database_url = os.environ["DATABASE_URL"]
        except KeyError as exc:
            raise RuntimeError(f"Missing required environment variable: {exc}") from exc
        return cls(
            token=token,
            database_url=database_url,
            docker_host=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock"),
            whitelist_path=Path(os.environ.get("WHITELIST_PATH", "config/whitelist.yml")),
        )


@dataclass(frozen=True)
class Whitelist:
    """Allowed guilds, each mapped to its allowed channel IDs (empty set = all)."""

    guilds: dict[int, frozenset[int]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Whitelist":
        data = yaml.safe_load(path.read_text()) or {}
        guilds: dict[int, frozenset[int]] = {}
        for entry in data.get("guilds") or []:
            guild_id = int(entry["id"])
            channels = frozenset(int(c) for c in entry.get("channels") or [])
            guilds[guild_id] = channels
        if not guilds:
            raise RuntimeError(f"Whitelist at {path} contains no guilds")
        return cls(guilds=guilds)

    @property
    def guild_ids(self) -> list[int]:
        return list(self.guilds)

    def allows(self, guild_id: int | None, channel_id: int | None) -> bool:
        if guild_id is None or guild_id not in self.guilds:
            return False
        allowed_channels = self.guilds[guild_id]
        return not allowed_channels or channel_id in allowed_channels
