"""Persist and read P4b shadow eligibility records."""

from __future__ import annotations

import json

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import PersonaTrait
from echomind.domain.trait_shadow_record import TraitShadowRecord


def _trait(row: aiosqlite.Row) -> PersonaTrait:
    return PersonaTrait(
        trait_id=int(row[0]), category=row[1], trait_text=str(row[2]),
        evidence_count=int(row[3]), contradiction_count=int(row[4]),
        strength=int(row[5]),
    )


def _shadow(row: aiosqlite.Row) -> TraitShadowRecord:
    return TraitShadowRecord(
        record_id=int(row[0]), chat_key=str(row[1]), session_id=str(row[2]),
        trait_ids=tuple(json.loads(row[3])), allowed_tools=tuple(json.loads(row[4])),
        allow_refusal=bool(row[5]), actual_tools=tuple(json.loads(row[6])),
        sent_count=int(row[7]), created_ms=int(row[8]),
    )


class SqliteTraitShadowStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def active_traits(self) -> tuple[PersonaTrait, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id, category, trait_text, evidence_count, contradiction_count, "
                "strength FROM persona_traits WHERE status='active' ORDER BY id"
            )
            return tuple(_trait(row) for row in await cursor.fetchall())

    async def record_shadow(self, record: TraitShadowRecord) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT INTO trait_action_shadow "
                "(chat_key, session_id, trait_ids_json, allowed_tools_json, "
                "allow_refusal, actual_tools_json, sent_count, created_ms) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (record.chat_key, record.session_id,
                 json.dumps(record.trait_ids), json.dumps(record.allowed_tools),
                 int(record.allow_refusal), json.dumps(record.actual_tools),
                 record.sent_count, record.created_ms),
            )
            await conn.commit()

    async def list_shadow(
        self, chat_key: str, limit: int = 50
    ) -> tuple[TraitShadowRecord, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id, chat_key, session_id, trait_ids_json, allowed_tools_json, "
                "allow_refusal, actual_tools_json, sent_count, created_ms "
                "FROM trait_action_shadow WHERE chat_key=? ORDER BY id DESC LIMIT ?",
                (chat_key, limit),
            )
            return tuple(_shadow(row) for row in await cursor.fetchall())
