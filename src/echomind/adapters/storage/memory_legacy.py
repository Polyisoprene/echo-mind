"""Legacy semantic-fact query used when FACTS_V2 is explicitly disabled."""

from __future__ import annotations

from typing import Any

from echomind.adapters.storage import memory_cross_session as _cross
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_rows import row_to_fact
from echomind.domain.models import SemanticFact


async def load_legacy_facts(
    db: SqliteDatabase, chat_key: str, min_confidence: float,
    person_ids: tuple[str, ...], current: int,
) -> tuple[SemanticFact, ...]:
    clauses = ["chat_key IN (?, 'global')"]
    params: list[Any] = [chat_key]
    if chat_key.startswith("private:"):
        clauses.append("(scope='person' AND owner_id=?)")
        params.append(chat_key.split(":", 1)[1])
    if person_ids:
        marks = ",".join("?" for _ in person_ids)
        clauses.append(
            f"(scope='person' AND (owner_id IN ({marks})"
            f" OR source_person_id IN ({marks})))"
        )
        params.extend(person_ids * 2)
    where = " OR ".join(clauses)
    privacy = ("(sensitivity IN ('public','group') OR (sensitivity='private' "
               "AND ? IN (chat_key, 'private:'||owner_id)))")
    sql = (
        f"SELECT {_cross.FACT_COLUMNS} FROM semantic_facts WHERE ({where}) AND confidence >= ? "  # noqa: S608
        f"AND {privacy} AND (event_time_ms = 0 OR event_time_ms <= ?) "
        "AND (valid_to_ms IS NULL OR valid_to_ms > ?) "
        "ORDER BY is_locked DESC, confidence DESC, id DESC"
    )
    async with db.connect() as conn:
        cursor = await conn.execute(
            sql, (*params, min_confidence, chat_key, current, current)
        )
        rows = await cursor.fetchall()
    return tuple(row_to_fact(r) for r in rows)
