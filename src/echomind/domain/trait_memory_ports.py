"""Narrow port for trait-to-memory links and their ranker scores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from echomind.domain.trait_memory_link import TraitMemoryLink


@runtime_checkable
class ITraitMemoryLinkStore(Protocol):
    async def link(self, link: TraitMemoryLink) -> None: ...

    async def list_links(
        self, trait_id: int, limit: int = 50
    ) -> tuple[TraitMemoryLink, ...]: ...

    async def ranker_scores(
        self, trait_ids: tuple[int, ...], memory_kind: str = "semantic"
    ) -> dict[int, float]: ...
