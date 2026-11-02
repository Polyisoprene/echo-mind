"""Port for listing conversations available to an outbound sender."""

from __future__ import annotations

from typing import Protocol


class IGroupDirectory(Protocol):
    async def list_groups(self) -> tuple[dict[str, object], ...]: ...
