"""Stage 39 S39-3: read side for claims (infra stays out of the mind layer)."""

from __future__ import annotations

import json
import math
import os
from typing import Literal, cast

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import SemanticFact
from echomind.mind.fact_shadow import ClaimView


def facts_v2_enabled() -> bool:
    """Whether reads should come from the claim store instead of legacy facts."""
    return os.getenv("FACTS_V2", "off").lower() == "on"


_SQL = (
    "SELECT c.subject, c.value, c.predicate, c.recorded_at_ms, "
    "SUM(e.weight), MAX(CASE WHEN e.source_type='operator' THEN 1 ELSE 0 END), "
    "c.chat_key, c.scope, c.source_person_id, c.owner_id, c.sensitivity, "
    "c.audience_json, c.source_quote, c.source_turn_id, c.slot_key "
    "FROM claims c JOIN claim_evidence e ON e.claim_id=c.id "
    "WHERE c.chat_key IN (?, 'global') AND c.status='asserted' "
    "AND c.valid_from_ms <= ? AND (c.valid_to_ms IS NULL OR c.valid_to_ms > ?) "
    "GROUP BY c.id"
)


async def load_claim_views(
    db: SqliteDatabase, chat_key: str, now_ms: int = 0,
) -> list[ClaimView]:
    """Read asserted claims with summed evidence weight and operator provenance."""
    async with db.connect() as conn:
        cursor = await conn.execute(_SQL, (chat_key, now_ms, now_ms))
        rows = list(await cursor.fetchall())
    return [
        ClaimView(
            subject=str(r[0]), value=str(r[1]), predicate=str(r[2]),
            belief=round(1.0 - math.exp(-float(r[4] or 0.0)), 4),
            recorded_at_ms=int(r[3] or 0), locked=bool(r[5]),
            chat_key=str(r[6]),
            scope=cast(Literal["venue", "person", "global"], str(r[7])),
            source_person_id=str(r[8]), owner_id=str(r[9]),
            sensitivity=cast(
                Literal["public", "group", "private", "secret"], str(r[10])
            ),
            audience=tuple(str(p) for p in json.loads(str(r[11] or "[]")) if p),
            source_quote=str(r[12]), source_turn_id=str(r[13]),
            slot_key=str(r[14]),
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
                chat_key=view.chat_key, subject=view.subject, fact_text=view.value,
                confidence=min(1.0, view.belief),
                is_locked=view.locked, source="owner" if view.locked else "explored",
                scope=view.scope, source_person_id=view.source_person_id,
                owner_id=view.owner_id, sensitivity=view.sensitivity,
                audience=view.audience, source_quote=view.source_quote,
                source_turn_id=view.source_turn_id,
            ))
    return tuple(facts)


async def load_claim_facts(db: SqliteDatabase, chat_key: str) -> tuple[SemanticFact, ...]:
    """Read claims for one chat (plus global) as SemanticFact rows."""
    return claims_as_facts(await load_claim_views(db, chat_key))


def claimed_facts(
    views: list[ClaimView], min_confidence: float, person_ids: tuple[str, ...],
) -> tuple[SemanticFact, ...]:
    """Project claims through the same confidence/privacy/person filters as facts."""
    facts = claims_as_facts(views)
    return tuple(
        fact for fact in facts
        if fact.confidence >= min_confidence
        and fact.sensitivity in ("public", "group")
        and (not person_ids or (
            fact.scope == "person"
            and (fact.owner_id in person_ids or fact.source_person_id in person_ids)
        ))
    )


async def load_claim_facts_filtered(
    db: SqliteDatabase, chat_key: str, min_confidence: float,
    person_ids: tuple[str, ...], now_ms: int,
) -> tuple[SemanticFact, ...]:
    """Load claims and apply the same confidence/privacy/person filters as facts."""
    views = await load_claim_views(db, chat_key, now_ms)
    return claimed_facts(views, min_confidence, person_ids)
