"""Stage 39 S39-3: read side for claims (infra stays out of the mind layer)."""

from __future__ import annotations

import json
import math
import os
from typing import Any, Literal, cast

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_cross_session import merge_cross_session
from echomind.domain.models import SemanticFact
from echomind.mind.fact_shadow import ClaimView


def facts_v2_enabled() -> bool:
    """Whether reads should come from the claim store instead of legacy facts."""
    return os.getenv("FACTS_V2", "on").lower() == "on"


_SQL = (
    "SELECT c.subject, c.value, c.predicate, c.recorded_at_ms, "
    "SUM(e.weight), MAX(CASE WHEN e.source_type='operator' THEN 1 ELSE 0 END), "
    "c.chat_key, c.scope, c.source_person_id, c.owner_id, c.sensitivity, "
    "c.audience_json, c.source_quote, c.source_turn_id, c.slot_key, c.id, "
    "c.event_time_ms, c.confidence, c.revision_count "
    "FROM claims c JOIN claim_evidence e ON e.claim_id=c.id "
    "WHERE c.chat_key IN (?, 'global') AND c.status='asserted' "
    "AND c.valid_from_ms <= ? AND (c.valid_to_ms IS NULL OR c.valid_to_ms > ?) "
    "GROUP BY c.id"
)


def _claim_scope(chat_key: str, person_ids: tuple[str, ...]) -> tuple[str, list[object]]:
    where = "c.chat_key IN (?, 'global')"
    params: list[object] = [chat_key]
    if chat_key.startswith("private:"):
        where += " OR (c.sensitivity='private' AND c.owner_id=?)"
        params.append(chat_key.split(":", 1)[1])
    if person_ids:
        marks = ",".join("?" for _ in person_ids)
        where += f" OR (c.scope='person' AND (c.owner_id IN ({marks})"
        where += f" OR c.source_person_id IN ({marks})))"
        params.extend(person_ids * 2)
    return where, params


async def load_claim_views(
    db: SqliteDatabase, chat_key: str, now_ms: int = 0,
    person_ids: tuple[str, ...] = (),
) -> list[ClaimView]:
    """Read asserted claims with summed evidence weight and operator provenance."""
    where, params = _claim_scope(chat_key, person_ids)
    sql = _SQL.replace("WHERE c.chat_key IN (?, 'global')", f"WHERE ({where})")
    async with db.connect() as conn:
        cursor = await conn.execute(sql, (*params, now_ms, now_ms))
        rows = list(await cursor.fetchall())
    return [_claim_view(r) for r in rows]


def _claim_view(r: object) -> ClaimView:
    row = cast(tuple[Any, ...], r)
    return ClaimView(
        subject=str(row[0]), value=str(row[1]), predicate=str(row[2]),
        belief=round(1.0 - math.exp(-float(row[4] or 0.0)), 4),
        recorded_at_ms=int(row[3] or 0), locked=bool(row[5]),
        chat_key=str(row[6]),
        scope=cast(Literal["venue", "person", "global"], str(row[7])),
        source_person_id=str(row[8]), owner_id=str(row[9]),
        sensitivity=cast(
            Literal["public", "group", "private", "secret"], str(row[10])
        ),
        audience=tuple(str(p) for p in json.loads(str(row[11] or "[]")) if p),
        source_quote=str(row[12]), source_turn_id=str(row[13]),
        slot_key=str(row[14]), claim_id=int(row[15]),
        event_time_ms=int(row[16] or 0), confidence=float(row[17] or 0.0),
        revision_count=int(row[18] or 1),
    )

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
                fact_id=view.claim_id,
                chat_key=view.chat_key, subject=view.subject, fact_text=view.value,
                confidence=min(1.0, view.confidence or view.belief),
                revision_count=view.revision_count,
                is_locked=view.locked, source="owner" if view.locked else "explored",
                scope=view.scope, source_person_id=view.source_person_id,
                owner_id=view.owner_id, sensitivity=view.sensitivity,
                audience=view.audience, source_quote=view.source_quote,
                source_turn_id=view.source_turn_id,
                source_venue_id=view.chat_key,
                event_time_ms=view.event_time_ms,
            ))
    return tuple(facts)


def _private_visible(fact: SemanticFact, chat_key: str) -> bool:
    if fact.sensitivity != "private":
        return fact.sensitivity in ("public", "group")
    if fact.chat_key == chat_key:
        return True
    return (
        fact.scope == "person" and chat_key.startswith("private:")
        and fact.owner_id == chat_key.split(":", 1)[1]
    )


def _person_visible(fact: SemanticFact, person_ids: tuple[str, ...]) -> bool:
    if not person_ids or fact.scope != "person":
        return True
    return fact.owner_id in person_ids or fact.source_person_id in person_ids


def _fact_visible(
    fact: SemanticFact, min_confidence: float, person_ids: tuple[str, ...],
    chat_key: str, now_ms: int,
) -> bool:
    return (
        fact.confidence >= min_confidence
        and (fact.event_time_ms == 0 or fact.event_time_ms <= now_ms)
        and _private_visible(fact, chat_key)
        and _person_visible(fact, person_ids)
    )


def claimed_facts(
    views: list[ClaimView], min_confidence: float, person_ids: tuple[str, ...],
    chat_key: str = "", now_ms: int = 0,
) -> tuple[SemanticFact, ...]:
    """Project claims through the same confidence/privacy/person filters as facts."""
    return tuple(
        fact for fact in claims_as_facts(views)
        if _fact_visible(fact, min_confidence, person_ids, chat_key, now_ms)
    )

async def load_claim_facts_filtered(
    db: SqliteDatabase, chat_key: str, min_confidence: float,
    person_ids: tuple[str, ...], now_ms: int,
) -> tuple[SemanticFact, ...]:
    """Load claims and apply the same confidence/privacy/person filters as facts."""
    views = await load_claim_views(db, chat_key, now_ms, person_ids)
    return claimed_facts(views, min_confidence, person_ids, chat_key, now_ms)


async def load_claim_facts_cross(
    db: SqliteDatabase, chat_key: str, min_confidence: float,
    person_ids: tuple[str, ...], now_ms: int,
) -> tuple[SemanticFact, ...]:
    facts = await load_claim_facts_filtered(db, chat_key, min_confidence, person_ids, now_ms)
    return await merge_cross_session(db, chat_key, facts, min_confidence, now_ms)
