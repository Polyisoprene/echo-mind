"""Trait lifecycle from evidence: candidate/active/retired.

Dormant is deliberately not assigned yet: it needs a sourced inactivity policy,
not an arbitrary wall-clock cutoff. Shadow mode only computes status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TraitStatus = Literal["candidate", "active", "dormant", "retired", "legacy_unverified"]


@dataclass(frozen=True)
class TraitEvidenceStats:
    support_contexts: frozenset[str]
    contradiction_contexts: frozenset[str]
    last_support_ms: int = 0
    last_contradiction_ms: int = 0

    @property
    def supports(self) -> int:
        return len(self.support_contexts)

    @property
    def contradictions(self) -> int:
        return len(self.contradiction_contexts)


@dataclass(frozen=True)
class TraitLifecycle:
    status: TraitStatus
    posterior: float
    reason: str


def assess_lifecycle(stats: TraitEvidenceStats) -> TraitLifecycle:
    """Beta(1+s, 1+c) decision: two independent contexts + posterior > 0.5."""
    supports, contradictions = stats.supports, stats.contradictions
    if supports == 0 and contradictions == 0:
        return TraitLifecycle("legacy_unverified", 0.5, "no evidence")
    posterior = (1.0 + supports) / (2.0 + supports + contradictions)
    if supports >= 2 and posterior > 0.5:
        return TraitLifecycle("active", posterior, "two independent contexts")
    if contradictions > 0 and posterior <= 0.5:
        return TraitLifecycle("retired", posterior, "contradicted")
    return TraitLifecycle("candidate", posterior, "insufficient independent evidence")
