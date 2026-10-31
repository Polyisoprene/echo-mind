"""Memory-related ports kept out of the main ports module's line budget."""

from __future__ import annotations

from typing import Protocol

from echomind.domain.relation import MemoryRelation


class IMemoryVectorStore(Protocol):
    """Read-side port for persisted memory vectors."""

    async def get(
        self, memory_kind: str, memory_ids: tuple[int, ...], model: str = ""
    ) -> dict[int, tuple[float, ...]]: ...


class IRelationStore(Protocol):
    """Read side of typed memory relations."""

    async def neighbors(self, subject_id: str) -> tuple[MemoryRelation, ...]: ...

    async def reachable(self, starts: tuple[str, ...], max_hops: int = 2) -> set[str]: ...


class IEmbeddingGateway(Protocol):
    """OpenAI-compatible text embedding gateway."""

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


__all__ = ["IEmbeddingGateway", "IMemoryVectorStore", "IRelationStore"]
