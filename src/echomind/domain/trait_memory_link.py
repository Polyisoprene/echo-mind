"""Auditable links between an active trait and a memory item."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from echomind.domain.base import FrozenValueObject


class TraitMemoryLink(FrozenValueObject):
    link_id: int = 0
    trait_id: int = Field(ge=1)
    memory_kind: Literal["semantic", "episodic"]
    memory_id: int = Field(ge=1)
    relation: Literal["supports", "contradicts"] = "supports"
    evidence_ms: int = 0
