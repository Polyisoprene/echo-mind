"""Stage 39 S39-3: read side for claims (infra stays out of the mind layer)."""

from __future__ import annotations

import math

from echomind.adapters.storage.database import SqliteDatabase
from echomind.mind.fact_shadow import ClaimView

_SQL = (
    "SELECT c.id, c.subject, c.value, c.predicate, c.recorded_at_ms, "
    "SUM(e.weight), MAX(CASE WHEN e.source_type='operator' THEN 1 ELSE 0 END) "
    "FROM claims c JOIN claim_evidence e ON e.claim_id=c.id "
    "WHERE c.chat_key IN (?, 'global') AND c.status='asserted' GROUP BY c.id"
)


async def load_claim_views(db: SqliteDatabase, chat_key: str) -> list[ClaimView]:
    """Read asserted claims with summed evidence weight and operator provenance."""
    async with db.connect() as conn:
        cursor = await conn.execute(_SQL, (chat_key,))
        rows = list(await cursor.fetchall())
    return [
        ClaimView(
            subject=str(r[1]), value=str(r[2]), predicate=str(r[3]),
            belief=round(1.0 - math.exp(-float(r[5] or 0.0)), 4),
            recorded_at_ms=int(r[4] or 0), locked=bool(r[6]),
        )
        for r in rows
    ]
