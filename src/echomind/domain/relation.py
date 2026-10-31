"""Typed, directed memory relations (subject --predicate--> object)."""

from __future__ import annotations

from echomind.domain.base import FrozenValueObject

PPR_DAMPING = 0.85
PPR_ITERATIONS = 100
PPR_TOL = 1e-6


class MemoryRelation(FrozenValueObject):
    relation_id: int = 0
    subject_id: str
    predicate: str
    object_id: str
    valid_from_ms: int = 0
    valid_to_ms: int | None = None
    source_memory_id: int = 0
    confidence: float = 0.8


__all__ = ["PPR_DAMPING", "PPR_ITERATIONS", "PPR_TOL", "MemoryRelation"]
