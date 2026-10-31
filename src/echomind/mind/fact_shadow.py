"""Stage 39 S39-3: shadow comparison between legacy fact recall and the claim store."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from echomind.domain.models import SemanticFact
from echomind.mind.ebbinghaus import _fact_relevance_score, tokenize_query

MS_PER_DAY = 86_400_000.0


@dataclass(frozen=True)
class ClaimView:
    """One asserted claim with its posterior and provenance."""

    subject: str
    value: str
    predicate: str
    belief: float
    recorded_at_ms: int
    locked: bool


def _key(subject: str, value: str) -> str:
    return f"{subject}：{value}"


def claim_rank(views: list[ClaimView], query: str, limit: int, now_ms: int) -> list[str]:
    """Rank claims by relevance + posterior + recency, one line per subject/predicate."""
    tokens = tokenize_query(query)
    low = query.lower()
    scored: dict[str, tuple[float, str]] = {}
    for view in views:
        fact_like = SemanticFact(
            chat_key="", subject=view.subject, fact_text=view.value,
            confidence=min(1.0, view.belief), is_locked=view.locked,
        )
        base = _fact_relevance_score(fact_like, tokens, low, query)
        age_days = 0.0
        if view.recorded_at_ms:
            age_days = max(0.0, (now_ms - view.recorded_at_ms) / MS_PER_DAY)
        score = base + 2.0 * view.belief + 1.5 * math.exp(-age_days / 7.0)
        slot = f"{view.subject}::{view.predicate}"
        line = _key(view.subject, view.value)
        if slot not in scored or score > scored[slot][0]:
            scored[slot] = (score, line)
    ranked = sorted(scored.values(), key=lambda item: -item[0])
    return [line for _, line in ranked[:limit]]


def compare(
    legacy_lines: list[str], claim_lines: list[str]
) -> dict[str, Any]:
    """Overlap metrics between the two rankings (same query)."""
    legacy, claims = set(legacy_lines), set(claim_lines)
    union = legacy | claims
    return {
        "legacy": legacy_lines, "claims": claim_lines,
        "overlap": len(legacy & claims),
        "ratio": round(len(legacy & claims) / max(1, len(union)), 3),
        "only_claims": sorted(claims - legacy), "only_legacy": sorted(legacy - claims),
    }
