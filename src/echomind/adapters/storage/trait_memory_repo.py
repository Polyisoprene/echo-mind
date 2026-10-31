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
        relation=cast(Any, str(row[4])), evidence_ms=int(row[5]),
    )


class SqliteTraitMemoryLinkStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def link(self, link: TraitMemoryLink) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO trait_memory_links "
                "(trait_id, memory_kind, memory_id, relation, evidence_ms) "
                "VALUES (?,?,?,?,?)",
                (link.trait_id, link.memory_kind, link.memory_id,
                 link.relation, link.evidence_ms),
            )
            await conn.commit()

    async def list_links(
        self, trait_id: int, limit: int = 50
    ) -> tuple[TraitMemoryLink, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id, trait_id, memory_kind, memory_id, relation, evidence_ms "
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
                "WHERE memory_kind=? AND relation='supports'",
                (memory_kind,),
            )
            return {
                int(row[1]): 1.0 for row in await cursor.fetchall()
                if int(row[0]) in wanted
            }
