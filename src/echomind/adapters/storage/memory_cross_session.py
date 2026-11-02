"""Cross-session fact candidates, filtered by source/audience policy."""

from __future__ import annotations

import time

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_rows import row_to_fact
from echomind.domain.models import SemanticFact
from echomind.mind.session_memory_policy import RecallRequest, can_recall_across_sessions

FACT_COLUMNS = (
    "id, chat_key, subject, fact_text, confidence, is_locked, source, revision_count, "
    "scope, source_person_id, source_venue_id, owner_id, sensitivity, audience_json, "
    "source_quote, source_turn_id, event_time_ms, valid_to_ms"
)


async def load_cross_session_facts(
    db: SqliteDatabase, chat_key: str, min_confidence: float = 0.0,
    now_ms: int | None = None,
) -> tuple[SemanticFact, ...]:
    current = int(time.time() * 1000) if now_ms is None else now_ms
    sql = (
        f"SELECT {FACT_COLUMNS} FROM semantic_facts "  # noqa: S608
        "WHERE sensitivity IN ('public','group') AND confidence >= ? "
        "AND (event_time_ms = 0 OR event_time_ms <= ?) "
        "AND (valid_to_ms IS NULL OR valid_to_ms > ?) "
        "ORDER BY is_locked DESC, confidence DESC, id DESC"
    )
    async with db.connect() as conn:
        rows = await (await conn.execute(sql, (min_confidence, current, current))).fetchall()
    facts = tuple(row_to_fact(row) for row in rows)
    return tuple(
        fact for fact in facts
        if can_recall_across_sessions(RecallRequest(
            source_chat=fact.chat_key, current_chat=chat_key,
            sensitivity=fact.sensitivity, audience=fact.audience,
        ))
    )
