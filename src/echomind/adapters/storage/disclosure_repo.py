"""Persist disclosure decisions and the 'who already knows' state."""

from __future__ import annotations

import json
import time

from echomind.adapters.storage.database import SqliteDatabase


class SqliteDisclosureLog:
    """Small adapter behind IDisclosureLog; kept out of the memory repo's line budget."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def log_disclosure(
        self, *, memory_kind: str, memory_id: int, venue: str,
        audience: tuple[str, ...], action: str, reason: str,
        phase: str = "gate", persona_json: str = "{}",
    ) -> None:
        sql = (
            "INSERT INTO disclosures "
            "(memory_kind, memory_id, venue, audience_json, action, reason, phase, "
            "persona_json, ts_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        async with self._db.connect() as conn:
            await conn.execute(sql, (
                memory_kind, memory_id, venue, json.dumps(list(audience)),
                action, reason, phase, persona_json, int(time.time() * 1000),
            ))
            await conn.commit()

    async def mark_known(
        self, memory_kind: str, memory_id: int, person_id: str,
        state: str, confidence: float = 1.0,
    ) -> None:
        sql = (
            "INSERT INTO memory_knowledge "
            "(memory_kind, memory_id, person_id, state, confidence, updated_ms) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(memory_kind, memory_id, person_id) "
            "DO UPDATE SET state=excluded.state, confidence=excluded.confidence, "
            "updated_ms=excluded.updated_ms"
        )
        async with self._db.connect() as conn:
            await conn.execute(
                sql, (memory_kind, memory_id, person_id, state, confidence,
                      int(time.time() * 1000)),
            )
            await conn.commit()

    async def grant(
        self, *, memory_kind: str, memory_id: int, grantee_id: str,
        granted_by: str, expires_ms: int | None = None,
    ) -> None:
        sql = (
            "INSERT INTO disclosure_grants "
            "(memory_kind, memory_id, grantee_id, granted_by, granted_ms, expires_ms) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(memory_kind, memory_id, grantee_id) DO UPDATE SET "
            "granted_by=excluded.granted_by, granted_ms=excluded.granted_ms, "
            "expires_ms=excluded.expires_ms"
        )
        async with self._db.connect() as conn:
            await conn.execute(sql, (
                memory_kind, memory_id, grantee_id, granted_by,
                int(time.time() * 1000), expires_ms,
            ))
            await conn.commit()

    async def has_grant(
        self, *, memory_kind: str, memory_id: int, grantee_id: str,
        now_ms: int | None = None,
    ) -> bool:
        now = int(time.time() * 1000) if now_ms is None else now_ms
        sql = (
            "SELECT 1 FROM disclosure_grants WHERE memory_kind=? AND memory_id=? "
            "AND grantee_id=? AND (expires_ms IS NULL OR expires_ms > ?)"
        )
        async with self._db.connect() as conn:
            row = await (await conn.execute(
                sql, (memory_kind, memory_id, grantee_id, now)
            )).fetchone()
        return row is not None

    async def prune(self, before_ms: int) -> int:
        """Delete disclosure rows older than the cutoff; returns the deleted count."""
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "DELETE FROM disclosures WHERE ts_ms < ?", (before_ms,)
            )
            await conn.commit()
        return int(cursor.rowcount)

    async def who_knows(
        self, memory_kind: str, memory_id: int
    ) -> tuple[tuple[str, str], ...]:
        sql = (
            "SELECT person_id, state FROM memory_knowledge "
            "WHERE memory_kind = ? AND memory_id = ? ORDER BY person_id"
        )
        async with self._db.connect() as conn:
            rows = await (await conn.execute(sql, (memory_kind, memory_id))).fetchall()
        return tuple((str(r[0]), str(r[1])) for r in rows)


__all__ = ["SqliteDisclosureLog"]
