"""Read-only view of host containers via the docker-socket-proxy.

The docker SDK is synchronous, so every call is pushed off the event loop
with asyncio.to_thread. All access goes through the proxy, which only
permits GET requests on container endpoints — writes are impossible.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import docker


@dataclass(frozen=True)
class ContainerStatus:
    name: str
    image: str
    status: str      # e.g. "running", "exited"
    state: str       # human string, e.g. "Up 3 hours"
    health: str | None


class DockerMonitor:
    def __init__(self, docker_host: str) -> None:
        self._client = docker.DockerClient(base_url=docker_host, timeout=10)

    async def ping(self) -> bool:
        return await asyncio.to_thread(self._client.ping)

    async def list_containers(self) -> list[ContainerStatus]:
        return await asyncio.to_thread(self._list_containers_sync)

    async def get_container(self, name: str) -> ContainerStatus | None:
        try:
            container = await asyncio.to_thread(self._client.containers.get, name)
        except docker.errors.NotFound:
            return None
        return self._to_status(container)

    def _list_containers_sync(self) -> list[ContainerStatus]:
        containers = self._client.containers.list(all=True)
        return sorted((self._to_status(c) for c in containers), key=lambda c: c.name)

    @staticmethod
    def _to_status(container: docker.models.containers.Container) -> ContainerStatus:
        # attrs differ by endpoint: list responses have a human "Status" string
        # and State as a plain string; inspect responses have a State dict.
        attrs = container.attrs
        state = attrs.get("State")
        health = state.get("Health", {}).get("Status") if isinstance(state, dict) else None
        human = attrs.get("Status") if isinstance(attrs.get("Status"), str) else container.status
        return ContainerStatus(
            name=container.name,
            image=container.image.tags[0] if container.image.tags else container.image.short_id,
            status=container.status,
            state=human,
            health=health,
        )
