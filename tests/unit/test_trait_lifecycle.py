"""P1: shadow lifecycle from distinct evidence contexts."""

from __future__ import annotations

from echomind.mind.trait_lifecycle import TraitEvidenceStats, assess_lifecycle


def test_no_evidence_is_legacy_unverified() -> None:
    result = assess_lifecycle(TraitEvidenceStats(frozenset(), frozenset()))
    assert result.status == "legacy_unverified"


def test_one_context_is_candidate() -> None:
    result = assess_lifecycle(TraitEvidenceStats(frozenset({"c1"}), frozenset()))
    assert result.status == "candidate" and result.posterior == 2 / 3


def test_two_independent_contexts_activate() -> None:
    result = assess_lifecycle(TraitEvidenceStats(frozenset({"c1", "c2"}), frozenset()))
    assert result.status == "active" and result.posterior == 3 / 4


def test_equal_contradiction_retires() -> None:
    result = assess_lifecycle(
        TraitEvidenceStats(frozenset({"c1", "c2"}), frozenset({"c3", "c4"}))
    )
    assert result.status == "retired" and result.posterior == 0.5


def test_only_contradiction_retires() -> None:
    result = assess_lifecycle(TraitEvidenceStats(frozenset(), frozenset({"c1"})))
    assert result.status == "retired" and result.posterior == 1 / 3
