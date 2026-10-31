"""Row mappers for persisted memory records."""

from __future__ import annotations

import json
from typing import Literal, cast

import aiosqlite

from echomind.domain.models import EpisodicCard, ProceduralRule, SemanticFact

SourceType = Literal["system", "owner", "explored", "peer"]
Scope = Literal["venue", "person", "global"]
Sensitivity = Literal["public", "group", "private", "secret"]


def _scope(value: object) -> Scope:
    text = str(value)
    return cast(Scope, text) if text in ("venue", "person", "global") else "venue"


def _sensitivity(value: object) -> Sensitivity:
    text = str(value)
    return cast(Sensitivity, text) if text in ("public", "group", "private", "secret") else "group"


def row_to_episodic(row: aiosqlite.Row) -> EpisodicCard:
    parts = json.loads(str(row[6] or "[]"))
    return EpisodicCard(
        card_id=int(row[0]),
        chat_key=str(row[1]),
        timestamp_ms=int(row[2]),
        msg_seq=int(row[3]),
        summary=str(row[4]),
        key_detail=str(row[5]),
        participants=tuple(str(p) for p in parts if p),
        importance=float(row[7]),
        pinned=bool(row[8]),
        rehearsals=int(row[9]),
        last_recalled_ms=int(row[10]),
        scope=_scope(row[11]), source_person_id=str(row[12]), source_venue_id=str(row[13]),
        owner_id=str(row[14]), sensitivity=_sensitivity(row[15]),
        audience=tuple(str(p) for p in json.loads(str(row[16] or "[]")) if p),
        source_quote=str(row[17]),
    )


def row_to_fact(row: aiosqlite.Row) -> SemanticFact:
    raw_src = str(row[6])
    src: SourceType = (
        cast(SourceType, raw_src) if raw_src in ("system", "owner", "explored", "peer") else "peer"
    )
    return SemanticFact(
        fact_id=int(row[0]),
        chat_key=str(row[1]),
        subject=str(row[2]),
        fact_text=str(row[3]),
        confidence=float(row[4]),
        is_locked=bool(row[5]),
        source=src,
        revision_count=int(row[7]),
        scope=_scope(row[8]), source_person_id=str(row[9]), source_venue_id=str(row[10]),
        owner_id=str(row[11]), sensitivity=_sensitivity(row[12]),
        audience=tuple(str(p) for p in json.loads(str(row[13] or "[]")) if p),
        source_quote=str(row[14]),
    )


def row_to_rule(row: aiosqlite.Row) -> ProceduralRule:
    return ProceduralRule(
        rule_id=int(row[0]),
        chat_key=str(row[1]),
        trigger_keyword=str(row[2]),
        trigger_user_id=str(row[3]),
        action_instruction=str(row[4]),
        strength=int(row[5]),
    )
