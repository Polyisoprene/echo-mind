"""Stage 39 S39-2: idempotent backfill of legacy semantic facts into claims/evidence."""

from __future__ import annotations

from typing import Any

from echomind.adapters.storage.claim_repo import SqliteClaimStore
from echomind.adapters.storage.database import SqliteDatabase

_FACT_SQL = (
    "SELECT id, chat_key, subject, fact_text, confidence, is_locked, source, updated_at "
    "FROM semantic_facts"
)


def source_kind(source: str, is_locked: bool) -> str:
    """Map a legacy fact source to an evidence kind (locked => operator evidence)."""
    if is_locked or source in ("owner", "operator"):
        return "operator"
    return source if source in ("system", "peer", "explored", "derived") else "peer"


async def _load_facts(db: SqliteDatabase, chat_key: str) -> list[Any]:
    sql: str = _FACT_SQL
    params: tuple[Any, ...] = ()
    if chat_key:
        sql += " WHERE chat_key = ?"
        params = (chat_key,)
    async with db.connect() as conn:
        cursor = await conn.execute(sql, params)
        return list(await cursor.fetchall())


async def _mirror(store: SqliteClaimStore, rows: list[Any]) -> tuple[int, int]:
    created = skipped = 0
    for fact_id, chat, subject, text, conf, locked, source, updated in rows:
        tag = f"backfill:{fact_id}"
        if await store.has_tag(tag):
            skipped += 1
            continue
        await store.assert_claim(
            str(chat), str(subject), "value", str(text or ""),
            source_type=source_kind(str(source or ""), bool(locked)),
            source_id=str(source or "legacy"), observed_at_ms=int(updated or 0),
            weight_scale=float(conf or 0.5), tag=tag,
        )
        created += 1
    return created, skipped


async def _health(db: SqliteDatabase) -> tuple[int, int]:
    async with db.connect() as conn:
        cursor = await conn.execute(
            "SELECT c.chat_key, c.subject, COUNT(DISTINCT c.value) FROM claims c "
            "WHERE c.status='asserted' GROUP BY c.chat_key, c.subject "
            "HAVING COUNT(DISTINCT c.value) > 1"
        )
        conflicts = len(list(await cursor.fetchall()))
        cursor = await conn.execute("SELECT COUNT(*) FROM claims WHERE status='asserted'")
        row = await cursor.fetchone()
    return (int(row[0]) if row else 0), conflicts


async def backfill_facts(db: SqliteDatabase, chat_key: str = "") -> dict[str, Any]:
    """Mirror every legacy fact once; return a health report (idempotent)."""
    store = SqliteClaimStore(db)
    await store.ensure_schema()
    rows = await _load_facts(db, chat_key)
    created, skipped = await _mirror(store, rows)
    claims, conflicts = await _health(db)
    return {
        "facts": len(rows), "created": created, "skipped": skipped,
        "claims": claims, "conflicts": conflicts,
        "locked": sum(1 for r in rows if r[5]),
    }
