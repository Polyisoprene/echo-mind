"""A generated trait candidate; never used by the live prompt until promoted."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from echomind.domain.base import FrozenValueObject

TraitCategory = Literal["habit", "temperament", "taste", "taboo"]
CandidateStatus = Literal["candidate", "rejected", "promoted"]


class TraitCandidate(FrozenValueObject):
    """LLM-proposed trait with the evidence quotes that justify it."""

    candidate_id: int = 0
    trait_id: int = Field(ge=1)
    category: TraitCategory
    trait_text: str = Field(min_length=1)
    evidence_json: str
    prompt_hash: str = Field(min_length=1)
    generator_model: str = ""
    status: CandidateStatus = "candidate"
    reject_reason: str = ""
    created_ms: int = Field(ge=0)
