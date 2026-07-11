"""Settings from environment variables and the guild/channel whitelist file."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    token: str
    database_url: str
    docker_host: str
    whitelist_path: Path
    blacklist_path: Path
    god_user_id: int | None  # sole user allowed to run /restart; None = nobody

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            token = os.environ["DISCORD_TOKEN"]
            database_url = os.environ["DATABASE_URL"]
        except KeyError as exc:
            raise RuntimeError(f"Missing required environment variable: {exc}") from exc
        god_raw = os.environ.get("GOD_USER", "").strip()
        try:
            god_user_id = int(god_raw) if god_raw else None
        except ValueError:
            raise RuntimeError(
                f"GOD_USER must be a numeric Discord user ID, got {god_raw!r}"
            ) from None
        return cls(
            token=token,
            database_url=database_url,
            docker_host=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock"),
            whitelist_path=Path(os.environ.get("WHITELIST_PATH", "config/whitelist.yml")),
            blacklist_path=Path(os.environ.get("BLACKLIST_PATH", "config/blacklist.yml")),
            god_user_id=god_user_id,
        )


@dataclass(frozen=True)
class Whitelist:
    """Allowed guilds/channels, and the container names /restart may touch.

    guilds maps guild ID -> allowed channel IDs (empty set = all channels).
    restartable holds compiled regexes; a container may be restarted only if
    one of them full-matches its name. Empty = no name restriction (temporary;
    the GOD_USER check is then the only gate on /restart).
    """

    guilds: dict[int, frozenset[int]] = field(default_factory=dict)
    restartable: tuple[re.Pattern[str], ...] = ()

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
        try:
            restartable = tuple(
                re.compile(p) for p in data.get("restartable_containers") or []
            )
        except re.error as exc:
            raise RuntimeError(f"Invalid regex in restartable_containers: {exc}") from exc
        return cls(guilds=guilds, restartable=restartable)

    @property
    def guild_ids(self) -> list[int]:
        return list(self.guilds)

    def allows(self, guild_id: int | None, channel_id: int | None) -> bool:
        if guild_id is None or guild_id not in self.guilds:
            return False
        allowed_channels = self.guilds[guild_id]
        return not allowed_channels or channel_id in allowed_channels

    def can_restart(self, container_name: str) -> bool:
        # TODO: make a non-empty whitelist mandatory again. Blank currently
        # means "no name restriction" — the GOD_USER gate is the only guard.
        if not self.restartable:
            return True
        return any(p.fullmatch(container_name) for p in self.restartable)


@dataclass(frozen=True)
class Blacklist:
    """Docker labels that hide a container from /containers, /container, and
    /restart autocomplete.

    Each entry is either "key=value" (label must have that exact value) or
    bare "key" (label must be present, any value). A container matching any
    entry is dropped. Containers with no labels at all — e.g. anything
    started with plain `docker run` outside this compose project — are never
    matched and always show up; label the containers you want hidden.
    """

    labels: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path) -> "Blacklist":
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text()) or {}
        return cls(labels=tuple(data.get("excluded_labels") or []))

    def hides(self, container_labels: dict[str, str]) -> bool:
        for entry in self.labels:
            key, _, value = entry.partition("=")
            if key not in container_labels:
                continue
            if not value or container_labels[key] == value:
                return True
        return False
