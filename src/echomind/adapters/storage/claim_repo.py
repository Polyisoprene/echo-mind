"""Stage 39 S39-1: claims + evidence store (shadow of the legacy fact table).

A fact is no longer one mutable row with a boolean lock: it is one or more claims, each
supported by weighted evidence, with a validity interval and a recorded-at timestamp.
"""

from __future__ import annotations

import math
import time
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.migrations import ensure_claim_tables

# Evidence base weights: calibrated so a single ordinary fact lands around 0.55,
# a repeated/peer fact around 0.5-0.7 and an operator/locked fact above 0.85.
SOURCE_WEIGHT = {
    "operator": 2.4, "system": 2.0, "derived": 1.2, "peer": 1.1, "explored": 1.0,
}
SOURCE_RELIABILITY = {
    "operator": 1.0, "system": 1.0, "derived": 1.0, "peer": 1.0, "explored": 1.0,
}
REVIEW_THRESHOLD = 3


def belief_of(weights: list[float]) -> float:
    """Map accumulated evidence weight to a [0, 1) posterior."""
    return round(1.0 - math.exp(-sum(max(0.0, w) for w in weights)), 4)


async def mirror_fact(
    db: SqliteDatabase, *, chat_key: str, subject: str, value: str,
    source: str, is_locked: bool, now_ms: int,
) -> None:
    """Dual-write a legacy semantic fact into the claim store (FACTS_V2_WRITE=on)."""
    import os

    if os.getenv("FACTS_V2_WRITE", "off").lower() != "on":
        return
    kind = "operator" if (is_locked or source in ("owner", "operator")) else source
    store = SqliteClaimStore(db)
    await store.assert_claim(
        chat_key, subject, "value", value, source_type=kind,
        source_id=source or kind, observed_at_ms=now_ms,
    )


class SqliteClaimStore:
    """Persist claims/evidence and expose belief, retraction and as-of lookup."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def ensure_schema(self) -> None:
        async with self._db.connect() as conn:
            await ensure_claim_tables(conn)
            await conn.commit()

    async def assert_claim(
        self, chat_key: str, subject: str, predicate: str, value: str, *,
        source_type: str = "system", source_id: str = "",
        observed_at_ms: int | None = None, valid_from_ms: int = 0,
        valid_to_ms: int | None = None, weight_scale: float = 1.0, tag: str = "",
    ) -> int:
        """Insert (or reuse) a claim and attach this piece of evidence to it."""
        now = int(time.time() * 1000) if observed_at_ms is None else observed_at_ms
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id FROM claims WHERE chat_key=? AND subject=? AND predicate=? "
                "AND value=? AND status='asserted' LIMIT 1",
                (chat_key, subject, predicate, value),
            )
            row = await cursor.fetchone()
            if row:
                claim_id = int(row[0])
            else:
                cursor = await conn.execute(
                    "INSERT INTO claims (chat_key, subject, predicate, value, valid_from_ms, "
                    "valid_to_ms, recorded_at_ms, status, created_by) "
                    "VALUES (?,?,?,?,?,?,?,'asserted',?)",
                    (chat_key, subject, predicate, value, valid_from_ms, valid_to_ms, now,
                     source_id or source_type),
                )
                claim_id = int(cursor.lastrowid or 0)
            await self._attach(
                conn, claim_id, source_type, source_id, now,
                weight_scale=weight_scale, tag=tag,
            )
            await self._review_conflicts(conn, chat_key, subject, predicate, claim_id)
            await conn.commit()
        return claim_id

    async def _attach(
        self, conn: Any, claim_id: int, source_type: str, source_id: str, now: int, *,
        weight_scale: float = 1.0, tag: str = "",
    ) -> None:
        base = SOURCE_WEIGHT.get(source_type, 1.0) * SOURCE_RELIABILITY.get(source_type, 1.0)
        # confidence scales between half and full weight, never zeroes the evidence out
        weight = base * (0.5 + 0.5 * max(0.0, min(1.0, weight_scale)))
        await conn.execute(
            "INSERT INTO claim_evidence (claim_id, source_type, source_id, weight, "
            "observed_at_ms, raw_text) VALUES (?,?,?,?,?,?)",
            (claim_id, source_type, source_id, round(weight, 4), now, tag),
        )

    async def _review_conflicts(
        self, conn: Any, chat_key: str, subject: str, predicate: str, claim_id: int
    ) -> None:
        """Open a review when >= N independent sources back a competing value."""
        cursor = await conn.execute(
            "SELECT DISTINCT c.value, e.source_id FROM claim_evidence e "
            "JOIN claims c ON c.id=e.claim_id WHERE c.chat_key=? AND c.subject=? "
            "AND c.predicate=? AND c.status='asserted' AND e.source_type='peer'",
            (chat_key, subject, predicate),
        )
        rows = [(str(r[0]), str(r[1])) for r in await cursor.fetchall()]
        cursor = await conn.execute(
            "SELECT DISTINCT value FROM claims WHERE chat_key=? AND subject=? "
            "AND predicate=? AND status='asserted'", (chat_key, subject, predicate),
        )
        values = {str(r[0]) for r in await cursor.fetchall()}
        if len(values) < 2 or len({src for _, src in rows}) < REVIEW_THRESHOLD:
            return
        exists = await conn.execute(
            "SELECT 1 FROM fact_reviews WHERE chat_key=? AND subject=? AND predicate=? "
            "AND resolved_at_ms IS NULL", (chat_key, subject, predicate),
        )
        if await exists.fetchone() is None:
            await conn.execute(
                "INSERT INTO fact_reviews (chat_key, subject, predicate, reason, opened_at_ms) "
                "VALUES (?,?,?,?,?)",
                (chat_key, subject, predicate, f"{len(rows)} peer sources disagree",
                 int(time.time() * 1000)),
            )

    async def has_tag(self, tag: str) -> bool:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM claim_evidence WHERE raw_text=? LIMIT 1", (tag,)
            )
            return await cursor.fetchone() is not None

    async def claim_belief(self, claim_id: int) -> float:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT weight FROM claim_evidence WHERE claim_id=?", (claim_id,)
            )
            weights = [float(r[0]) for r in await cursor.fetchall()]
        return belief_of(weights)

    async def claim_status(self, claim_id: int) -> str:
        async with self._db.connect() as conn:
            cursor = await conn.execute("SELECT status FROM claims WHERE id=?", (claim_id,))
            row = await cursor.fetchone()
        return str(row[0]) if row else ""

    async def retract(self, claim_id: int, reason: str = "") -> None:
        """Mark a claim retracted; history and evidence stay for audit."""
        async with self._db.connect() as conn:
            await conn.execute(
                "UPDATE claims SET status='retracted' WHERE id=?", (claim_id,)
            )
            await conn.execute(
                "INSERT INTO claim_evidence (claim_id, source_type, source_id, weight, "
                "observed_at_ms, raw_text) VALUES (?,?,?,?,?,?)",
                (claim_id, "operator", "retract", 0.0, int(time.time() * 1000), reason),
            )
            await conn.commit()

    async def open_reviews(self, chat_key: str) -> int:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM fact_reviews WHERE chat_key=? AND resolved_at_ms IS NULL",
                (chat_key,),
            )
            row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def current_value(self, chat_key: str, subject: str, *, as_of_ms: int = 0) -> str:
        """Highest-recorded claim valid at `as_of_ms` (0 = now)."""
        now = as_of_ms or int(time.time() * 1000)
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT value FROM claims WHERE chat_key=? AND subject=? AND status='asserted' "
                "AND valid_from_ms<=? AND (valid_to_ms IS NULL OR valid_to_ms>?) "
                "ORDER BY recorded_at_ms DESC LIMIT 1",
                (chat_key, subject, now, now),
            )
            row = await cursor.fetchone()
        return str(row[0]) if row else ""
