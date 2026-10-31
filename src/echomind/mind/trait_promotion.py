"""P2 promotion policy: structural review only; no automatic promotion."""

from __future__ import annotations

from dataclasses import dataclass

from echomind.domain.trait_candidate import TraitCandidate
from echomind.domain.trait_evidence import TraitEvidence


@dataclass(frozen=True)
class PromotionReview:
    eligible: bool
    reasons: tuple[str, ...]


def review_candidate(
    candidate: TraitCandidate, evidence: tuple[TraitEvidence, ...]
) -> PromotionReview:
    reasons: list[str] = []
    if candidate.status != "candidate":
        reasons.append(f"status={candidate.status}")
    if len({item.context_hash for item in evidence if item.polarity > 0}) < 2:
        reasons.append("need two independent support contexts")
    if not any(item.quote_kind != "tool" for item in evidence):
        reasons.append("need a behavioral/utterance quote, not tool-only")
    return PromotionReview(not reasons, tuple(reasons))
