"""Stage 39 S39-3: read side for claims (infra stays out of the mind layer)."""

from __future__ import annotations

import math
import os

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import SemanticFact
from echomind.mind.fact_shadow import ClaimView

def facts_v2_enabled() -> bool:
    """Whether reads should come from the claim store instead of legacy facts."""
    return os.getenv("FACTS_V2", "off").lower() == "on"


_SQL = (
    "SELECT c.id, c.subject, c.value, c.predicate, c.recorded_at_ms, "
    "SUM(e.weight), MAX(CASE WHEN e.source_type='operator' THEN 1 ELSE 0 END) "
    "FROM claims c JOIN claim_evidence e ON e.claim_id=c.id "
    "WHERE c.chat_key IN (?, 'global') AND c.status='asserted' GROUP BY c.id"
)


async def load_claim_views(db: SqliteDatabase, chat_key: str) -> list[ClaimView]:
    """Read asserted claims with summed evidence weight and operator provenance."""
    async with db.connect() as conn:
        cursor = await conn.execute(_SQL, (chat_key,))
        rows = list(await cursor.fetchall())
    return [
        ClaimView(
            subject=str(r[1]), value=str(r[2]), predicate=str(r[3]),
            belief=round(1.0 - math.exp(-float(r[5] or 0.0)), 4),
            recorded_at_ms=int(r[4] or 0), locked=bool(r[6]),
        )
        for r in rows
    ]


def claims_as_facts(views: list[ClaimView]) -> tuple[SemanticFact, ...]:
    """Convert claims into the SemanticFact shape the prompt layer already understands."""
    picked: dict[tuple[str, str], list[ClaimView]] = {}
    for view in views:
        picked.setdefault((view.subject, view.predicate), []).append(view)
    facts: list[SemanticFact] = []
    for (_subject, predicate), group in picked.items():
        group.sort(key=lambda v: (v.belief, v.recorded_at_ms), reverse=True)
        keep = group[:2] if predicate == "mentioned" else group[:1]
        for view in keep:
            facts.append(SemanticFact(
                chat_key="", subject=view.subject, fact_text=view.value,
                confidence=min(1.0, view.belief),
                is_locked=view.locked, source="owner" if view.locked else "explored",
            ))
    return tuple(facts)


async def load_claim_facts(db: SqliteDatabase, chat_key: str) -> tuple[SemanticFact, ...]:
    """Read claims for one chat (plus global) as SemanticFact rows."""
    return claims_as_facts(await load_claim_views(db, chat_key))
