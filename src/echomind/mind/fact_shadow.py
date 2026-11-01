"""Stage 39 S39-3: shadow comparison between legacy fact recall and the claim store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from echomind.domain.models import SemanticFact
from echomind.mind.ranker_fusion import unified_rank


@dataclass(frozen=True)
class ClaimView:
    """One asserted claim with its posterior and provenance."""

    subject: str
    value: str
    predicate: str
    belief: float
    recorded_at_ms: int
    locked: bool
    chat_key: str = ""
    scope: Literal["venue", "person", "global"] = "venue"
    source_person_id: str = ""
    owner_id: str = ""
    sensitivity: Literal["public", "group", "private", "secret"] = "group"
    audience: tuple[str, ...] = ()
    source_quote: str = ""
    source_turn_id: str = ""
    slot_key: str = ""


def _key(subject: str, value: str) -> str:
    return f"{subject}：{value}"


def claim_rank(views: list[ClaimView], query: str, limit: int, now_ms: int) -> list[str]:
    """Rank claims by the same ranker fusion as facts; one line per slot."""
    facts = tuple(
        SemanticFact(
            fact_id=index, chat_key="", subject=view.subject, fact_text=view.value,
            confidence=min(1.0, view.belief), is_locked=view.locked,
            event_time_ms=view.recorded_at_ms,
        )
        for index, view in enumerate(views, 1)
    )
    by_id = dict(enumerate(views, 1))
    ranked = unified_rank(
        facts, query, {}, {}, now_ms,
        disabled=frozenset({"order", "relations", "lock"}),
        force_recency=True,
    )
    seen: set[str] = set()
    lines: list[str] = []
    for fact in ranked:
        view = by_id[fact.fact_id]
        slot = f"{view.subject}::{view.predicate}"
        if slot in seen:
            continue
        seen.add(slot)
        lines.append(_key(view.subject, view.value))
        if len(lines) >= limit:
            break
    return lines


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
