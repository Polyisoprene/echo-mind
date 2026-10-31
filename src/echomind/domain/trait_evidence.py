"""Append-only trait evidence value object."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from echomind.domain.base import FrozenValueObject


class TraitEvidence(FrozenValueObject):
    """One piece of support/contradiction for a persona trait."""

    evidence_id: int = 0
    trait_id: int = Field(ge=1)
    session_id: str
    turn_id: str
    quote: str = Field(min_length=1)
    quote_kind: Literal["assistant", "user", "tool"]
    polarity: Literal[-1, 1] = 1
    context_hash: str = Field(min_length=1)
    created_ms: int = Field(ge=0)
