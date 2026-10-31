"""SQLite store for typed memory relations (P2)."""

from __future__ import annotations

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.relation import MemoryRelation


class SqliteRelationStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def upsert(self, relation: MemoryRelation) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT INTO memory_relations "
                "(subject_id, predicate, object_id, valid_from_ms, valid_to_ms, "
                "source_memory_id, confidence) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(subject_id, predicate, object_id) DO UPDATE SET "
                "valid_from_ms=excluded.valid_from_ms, valid_to_ms=excluded.valid_to_ms, "
                "source_memory_id=excluded.source_memory_id, confidence=excluded.confidence",
                (relation.subject_id, relation.predicate, relation.object_id,
                 relation.valid_from_ms, relation.valid_to_ms,
                 relation.source_memory_id, relation.confidence),
            )
            await conn.commit()

    async def neighbors(self, subject_id: str) -> tuple[MemoryRelation, ...]:
        async with self._db.connect() as conn:
            rows = await (await conn.execute(
                "SELECT id, subject_id, predicate, object_id, valid_from_ms, "
                "valid_to_ms, source_memory_id, confidence "
                "FROM memory_relations WHERE subject_id = ?", (subject_id,)
            )).fetchall()
        return tuple(
            MemoryRelation(
                relation_id=int(r[0]), subject_id=str(r[1]), predicate=str(r[2]),
                object_id=str(r[3]), valid_from_ms=int(r[4]),
                valid_to_ms=int(r[5]) if r[5] is not None else None,
                source_memory_id=int(r[6]), confidence=float(r[7]),
            )
            for r in rows
        )

    async def entities(self) -> tuple[str, ...]:
        async with self._db.connect() as conn:
            rows = await (await conn.execute(
                "SELECT subject_id FROM memory_relations UNION "
                "SELECT object_id FROM memory_relations"
            )).fetchall()
        return tuple(str(r[0]) for r in rows if str(r[0]))

    async def _objects(self, subject: str) -> set[str]:
        return {relation.object_id for relation in await self.neighbors(subject)}

    async def _next_frontier(self, frontier: set[str], seen: set[str]) -> set[str]:
        found: set[str] = set()
        for subject in frontier:
            found |= await self._objects(subject)
        return found - seen

    async def reachable(self, starts: tuple[str, ...], max_hops: int = 2) -> set[str]:
        seen: set[str] = set(starts)
        frontier: set[str] = set(starts)
        for _ in range(max_hops):
            frontier = await self._next_frontier(frontier, seen)
            seen |= frontier
            if not frontier:
                break
        return seen


__all__ = ["SqliteRelationStore"]
