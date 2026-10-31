"""Memory-related ports kept out of the main ports module's line budget."""

from __future__ import annotations

from typing import Protocol


class IMemoryVectorStore(Protocol):
    """Read-side port for persisted memory vectors."""

    async def get(
        self, memory_kind: str, memory_ids: tuple[int, ...]
    ) -> dict[int, tuple[float, ...]]: ...


class IEmbeddingGateway(Protocol):
    """OpenAI-compatible text embedding gateway."""

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


__all__ = ["IEmbeddingGateway", "IMemoryVectorStore"]
