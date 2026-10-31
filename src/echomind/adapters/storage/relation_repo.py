"""SQLite store for typed memory relations (P2)."""

from __future__ import annotations

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.relation import RELATION_MAX_HOPS, MemoryRelation


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

    async def neighbors(
        self, subject_id: str, now_ms: int = 0
    ) -> tuple[MemoryRelation, ...]:
        async with self._db.connect() as conn:
            rows = await (await conn.execute(
                "SELECT id, subject_id, predicate, object_id, valid_from_ms, "
                "valid_to_ms, source_memory_id, confidence "
                "FROM memory_relations WHERE subject_id = ? "
                "AND (valid_from_ms = 0 OR valid_from_ms <= ?) "
                "AND (valid_to_ms IS NULL OR valid_to_ms > ?)",
                (subject_id, now_ms, now_ms),
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

    async def _expand(
        self, subject: str, base: float, now_ms: int
    ) -> dict[str, float]:
        return {
            relation.object_id: base * relation.confidence
            for relation in await self.neighbors(subject, now_ms)
        }

    @staticmethod
    def _merge(
        target: dict[str, float], scores: dict[str, float], candidates: dict[str, float]
    ) -> None:
        for obj, candidate in candidates.items():
            if candidate > scores.get(obj, 0.0):
                scores[obj] = candidate
                target[obj] = max(target.get(obj, 0.0), candidate)

    async def reachable_scored(
        self, starts: tuple[str, ...], max_hops: int, now_ms: int
    ) -> dict[str, float]:
        scores: dict[str, float] = dict.fromkeys(starts, 1.0)
        frontier: dict[str, float] = dict(scores)
        for _ in range(max_hops):
            nxt: dict[str, float] = {}
            for subject, base in frontier.items():
                self._merge(nxt, scores, await self._expand(subject, base, now_ms))
            frontier = nxt
            if not frontier:
                break
        return scores

    async def reachable(
        self, starts: tuple[str, ...], max_hops: int = RELATION_MAX_HOPS,
        now_ms: int = 0,
    ) -> set[str]:
        return set(await self.reachable_scored(starts, max_hops, now_ms))


__all__ = ["SqliteRelationStore"]
