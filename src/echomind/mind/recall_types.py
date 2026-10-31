"""Retrieval-side decoration of an episodic card (Ebbinghaus retention + clarity)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from echomind.domain.models import EpisodicCard, FrozenValueObject


class RecalledMemoryItem(FrozenValueObject):
    """Episodic card decorated with real-time Ebbinghaus retention & clarity tier."""

    card: EpisodicCard
    retention: float = Field(ge=0.0, le=1.0)
    clarity: Literal["clear", "fuzzy"]


__all__ = ["RecalledMemoryItem"]
