"""Memory-related ports kept out of the main ports module's line budget."""

from __future__ import annotations

from typing import Protocol

from echomind.domain.relation import RELATION_MAX_HOPS, MemoryRelation


class IMemoryVectorStore(Protocol):
    """Read-side port for persisted memory vectors."""

    async def get(
        self, memory_kind: str, memory_ids: tuple[int, ...], model: str = ""
    ) -> dict[int, tuple[float, ...]]: ...


class IRelationStore(Protocol):
    """Read side of typed memory relations."""

    async def neighbors(
        self, subject_id: str, now_ms: int = 0
    ) -> tuple[MemoryRelation, ...]: ...

    async def reachable_scored(
        self, starts: tuple[str, ...], max_hops: int, now_ms: int
    ) -> dict[str, float]: ...

    async def reachable(
        self, starts: tuple[str, ...], max_hops: int = RELATION_MAX_HOPS,
        now_ms: int = 0,
    ) -> set[str]: ...

    async def entities(self) -> tuple[str, ...]: ...


class IEmbeddingGateway(Protocol):
    """OpenAI-compatible text embedding gateway."""

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


__all__ = ["IEmbeddingGateway", "IMemoryVectorStore", "IRelationStore"]
