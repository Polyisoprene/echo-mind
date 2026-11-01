"""B6: semantic facts expose an optional expiry and retrieval honors it."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.domain.models import SemanticFact


async def test_expired_and_future_facts_are_filtered(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "validity.db")
    await db.initialize()
    repo = SqliteMemoryRepository(db)
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="alive", fact_text="有效", event_time_ms=1,
    ))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="expired", fact_text="过期", event_time_ms=1,
        valid_to_ms=10,
    ))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="future", fact_text="未来", event_time_ms=5_000,
    ))
    facts = await repo.get_semantic_facts("g", now_ms=1_000)
    assert {fact.subject for fact in facts} == {"alive"}
