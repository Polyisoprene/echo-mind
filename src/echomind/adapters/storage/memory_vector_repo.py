"""Vector persistence for semantic memory retrieval (D15)."""

from __future__ import annotations

import json
import time

from echomind.adapters.storage.database import SqliteDatabase


class SqliteMemoryVectorStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def upsert(
        self, *, memory_kind: str, memory_id: int, model: str,
        vector: tuple[float, ...],
    ) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT INTO memory_vectors "
                "(memory_kind, memory_id, model, dim, vector_json, updated_ms) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(memory_kind, memory_id) "
                "DO UPDATE SET model=excluded.model, dim=excluded.dim, "
                "vector_json=excluded.vector_json, updated_ms=excluded.updated_ms",
                (memory_kind, memory_id, model, len(vector),
                 json.dumps(list(vector)), int(time.time() * 1000)),
            )
            await conn.commit()

    async def get(
        self, memory_kind: str, memory_ids: tuple[int, ...]
    ) -> dict[int, tuple[float, ...]]:
        if not memory_ids:
            return {}
        marks = ",".join("?" for _ in memory_ids)
        sql = (
            f"SELECT memory_id, vector_json FROM memory_vectors "  # noqa: S608
            f"WHERE memory_kind=? AND memory_id IN ({marks})"
        )
        async with self._db.connect() as conn:
            rows = await (await conn.execute(
                sql, (memory_kind, *memory_ids)
            )).fetchall()
        return {int(r[0]): tuple(float(x) for x in json.loads(str(r[1]))) for r in rows}

    async def load_all(self, memory_kind: str) -> dict[int, tuple[float, ...]]:
        async with self._db.connect() as conn:
            rows = await (await conn.execute(
                "SELECT memory_id, vector_json FROM memory_vectors WHERE memory_kind=?",
                (memory_kind,),
            )).fetchall()
        return {int(r[0]): tuple(float(x) for x in json.loads(str(r[1]))) for r in rows}


__all__ = ["SqliteMemoryVectorStore"]
