"""Manual review of cue-based sensitivity upgrades (D7)."""

from __future__ import annotations

import time

from echomind.adapters.storage.database import SqliteDatabase

ALLOWED = ("public", "group", "private", "secret")
_TABLES = {"semantic": "semantic_facts", "episodic": "episodic_memories"}


class SqliteSensitivityReviewer:
    """List and correct facts whose sensitivity was raised by a cue."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def list_flagged(self, memory_kind: str = "semantic") -> list[dict[str, object]]:
        table = _TABLES[memory_kind]
        sql = (
            f"SELECT id, subject, sensitivity, source_quote FROM {table} "  # noqa: S608
            "WHERE sensitivity IN ('private','secret') ORDER BY id"
        )
        async with self._db.connect() as conn:
            rows = await (await conn.execute(sql)).fetchall()
        return [
            {"id": int(r[0]), "subject": str(r[1]), "sensitivity": str(r[2]),
             "quote": str(r[3])}
            for r in rows
        ]

    async def apply(
        self, *, memory_kind: str, memory_id: int, to_sensitivity: str,
        reviewer: str, reason: str,
    ) -> str | None:
        """Return the previous sensitivity, or None when the row does not exist."""
        if memory_kind not in _TABLES or to_sensitivity not in ALLOWED:
            raise ValueError("invalid memory kind or sensitivity")
        table = _TABLES[memory_kind]
        async with self._db.connect() as conn:
            row = await (await conn.execute(
                f"SELECT sensitivity FROM {table} WHERE id = ?",  # noqa: S608
                (memory_id,),
            )).fetchone()
            if row is None:
                return None
            previous = str(row[0])
            await conn.execute(
                f"UPDATE {table} SET sensitivity = ? WHERE id = ?",  # noqa: S608
                (to_sensitivity, memory_id),
            )
            await conn.execute(
                "INSERT INTO sensitivity_reviews "
                "(memory_kind, memory_id, from_sensitivity, to_sensitivity, reviewer, "
                "reason, ts_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (memory_kind, memory_id, previous, to_sensitivity, reviewer, reason,
                 int(time.time() * 1000)),
            )
            await conn.commit()
        return previous


__all__ = ["SqliteSensitivityReviewer"]
