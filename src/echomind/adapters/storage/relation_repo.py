"""SQLite store for typed memory relations (P2)."""

from __future__ import annotations

from collections import defaultdict

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.relation import PPR_DAMPING, PPR_ITERATIONS, PPR_TOL, MemoryRelation


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

    async def _active_edges(self, now_ms: int) -> list[tuple[str, str, float]]:
        async with self._db.connect() as conn:
            rows = await (await conn.execute(
                "SELECT subject_id, object_id, confidence FROM memory_relations "
                "WHERE (valid_from_ms = 0 OR valid_from_ms <= ?) "
                "AND (valid_to_ms IS NULL OR valid_to_ms > ?)",
                (now_ms, now_ms),
            )).fetchall()
        return [(str(s), str(o), max(0.0, float(c))) for s, o, c in rows]

    @staticmethod
    def _adjacency(edges: list[tuple[str, str, float]]) -> dict[str, list[tuple[str, float]]]:
        outgoing: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for subject, obj, confidence in edges:
            outgoing[subject].append((obj, confidence))
        return outgoing

    @staticmethod
    def _initial(nodes: list[str], starts: tuple[str, ...]) -> dict[str, float]:
        scores = dict.fromkeys(nodes, 0.0)
        for start in starts:
            if start in scores:
                scores[start] += 1.0 / max(1, len(starts))
        return scores

    @staticmethod
    def _distribute(score: float, links: list[tuple[str, float]],
                    nxt: dict[str, float]) -> None:
        total = sum(weight for _, weight in links) or 1.0
        for obj, weight in links:
            nxt[obj] += PPR_DAMPING * score * weight / total

    def _step(self, scores: dict[str, float], nodes: list[str],
              outgoing: dict[str, list[tuple[str, float]]]) -> dict[str, float]:
        base = (1.0 - PPR_DAMPING) / len(nodes)
        nxt = dict.fromkeys(nodes, base)
        dangling = 0.0
        for node, score in scores.items():
            links = outgoing.get(node, [])
            if not links:
                dangling += score
                continue
            self._distribute(score, links, nxt)
        if dangling:
            for node in nodes:
                nxt[node] += PPR_DAMPING * dangling / len(nodes)
        return nxt

    async def ppr(self, starts: tuple[str, ...], now_ms: int) -> dict[str, float]:
        """Personalized PageRank over active, confidence-weighted edges."""
        edges = await self._active_edges(now_ms)
        nodes = sorted({node for s, o, _ in edges for node in (s, o)})
        if not nodes:
            return {}
        outgoing = self._adjacency(edges)
        scores = self._initial(nodes, starts)
        for _ in range(PPR_ITERATIONS):
            nxt = self._step(scores, nodes, outgoing)
            delta = sum(abs(nxt[node] - scores[node]) for node in nodes)
            scores = nxt
            if delta < PPR_TOL:
                break
        return scores

__all__ = ["SqliteRelationStore"]
