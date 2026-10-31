"""Promotion is structural review + explicit approval, never automatic."""

from __future__ import annotations

from echomind.domain.trait_candidate import TraitCandidate
from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.trait_promotion import review_candidate


def _candidate(status: str = "candidate") -> TraitCandidate:
    return TraitCandidate(
        trait_id=1, category="habit", trait_text="会先看细节",
        evidence_json="[]", prompt_hash="h", status=status,  # type: ignore[arg-type]
        created_ms=1,
    )


def _evidence(context: str, kind: str) -> TraitEvidence:
    return TraitEvidence(
        evidence_id=1, trait_id=1, session_id="s", turn_id="t", quote="q",
        quote_kind=kind, polarity=1, context_hash=context, created_ms=1,  # type: ignore[arg-type]
    )


def test_two_contexts_and_behavioral_quote_are_eligible() -> None:
    review = review_candidate(
        _candidate(), (_evidence("c1", "assistant"), _evidence("c2", "assistant"))
    )
    assert review.eligible is True


def test_tool_only_is_not_eligible() -> None:
    review = review_candidate(
        _candidate(), (_evidence("c1", "tool"), _evidence("c2", "tool"))
    )
    assert review.eligible is False


def test_one_context_and_promoted_status_are_not_eligible() -> None:
    assert review_candidate(_candidate(), (_evidence("c1", "assistant"),)).eligible is False
    assert review_candidate(
        _candidate("promoted"), (_evidence("c1", "assistant"), _evidence("c2", "assistant"))
    ).eligible is False
