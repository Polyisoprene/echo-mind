"""Persist trait-memory links and project them to equal-weight RRF scores."""

from __future__ import annotations

from typing import Any, cast

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.trait_memory_link import TraitMemoryLink


def _row(row: aiosqlite.Row) -> TraitMemoryLink:
    return TraitMemoryLink(
        link_id=int(row[0]), trait_id=int(row[1]),
        memory_kind=cast(Any, str(row[2])), memory_id=int(row[3]),
        relation=cast(Any, str(row[4])), is_context=bool(row[5]),
        evidence_ms=int(row[6]),
    )


class SqliteTraitMemoryLinkStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def link(self, link: TraitMemoryLink) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO trait_memory_links "
                "(trait_id, memory_kind, memory_id, relation, is_context, evidence_ms) "
                "VALUES (?,?,?,?,?,?)",
                (link.trait_id, link.memory_kind, link.memory_id,
                 link.relation, int(link.is_context), link.evidence_ms),
            )
            await conn.commit()

    async def list_links(
        self, trait_id: int, limit: int = 50
    ) -> tuple[TraitMemoryLink, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id, trait_id, memory_kind, memory_id, relation, is_context, "
                "evidence_ms "
                "FROM trait_memory_links WHERE trait_id=? ORDER BY id DESC LIMIT ?",
                (trait_id, limit),
            )
            return tuple(_row(row) for row in await cursor.fetchall())

    async def ranker_scores(
        self, trait_ids: tuple[int, ...], memory_kind: str = "semantic"
    ) -> dict[int, float]:
        """Support links produce presence scores only; no hand-tuned weights."""
        ids = tuple(dict.fromkeys(int(item) for item in trait_ids if item > 0))
        if not ids:
            return {}
        wanted = set(ids)
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT trait_id, memory_id FROM trait_memory_links "
                "WHERE memory_kind=? AND relation='supports' AND is_context=0",
                (memory_kind,),
            )
            return {
                int(row[1]): 1.0 for row in await cursor.fetchall()
                if int(row[0]) in wanted
            }
    async def link_turn_support(self, chat_key: str, turn_id: str) -> int:
        """A fact from the same turn is precise support evidence, not context."""
        if not turn_id:
            return 0
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "INSERT INTO trait_memory_links "
                "(trait_id, memory_kind, memory_id, relation, is_context, evidence_ms) "
                "SELECT e.trait_id, 'semantic', f.id, 'supports', 0, e.created_ms "
                "FROM trait_evidence e JOIN semantic_facts f "
                "ON f.source_turn_id = e.turn_id AND f.chat_key = ? "
                "WHERE e.turn_id = ? "
                "ON CONFLICT(trait_id, memory_kind, memory_id, relation) DO UPDATE SET "
                "is_context=0, evidence_ms=excluded.evidence_ms",
                (chat_key, turn_id),
            )
            await conn.commit()
            return int(cursor.rowcount)
