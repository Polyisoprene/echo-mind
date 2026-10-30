"""Stage 39 S39-2: legacy facts must backfill once, keep lock semantics and flag conflicts."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.claim_backfill import backfill_facts, source_kind
from echomind.adapters.storage.claim_repo import SqliteClaimStore
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import SemanticFact


async def _seed(db: SqliteDatabase) -> None:
    from echomind.adapters.storage.memory_repo import SqliteMemoryRepository

    repo = SqliteMemoryRepository(db)
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="群主", fact_text="群主是 A", confidence=0.9,
        is_locked=True, source="system",
    ))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="管理员", fact_text="管理员是 B", confidence=0.6, source="peer",
    ))


async def test_backfill_is_idempotent(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "bf.db")
    await db.initialize()
    await _seed(db)
    first = await backfill_facts(db)
    second = await backfill_facts(db)
    assert first["created"] == 2 and first["facts"] >= 1
    assert second["created"] == 0 and second["skipped"] == first["created"]


async def test_backfill_keeps_operator_evidence_for_locked(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "bf2.db")
    await db.initialize()
    await _seed(db)
    await backfill_facts(db)
    import sqlite3

    con = sqlite3.connect(str(tmp_path / "bf2.db"))
    kinds = {r[0] for r in con.execute("SELECT source_type FROM claim_evidence")}
    assert "operator" in kinds and "peer" in kinds


async def test_backfill_reports_conflict(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "bf3.db")
    await db.initialize()
    await _seed(db)
    store = SqliteClaimStore(db)
    await store.assert_claim("g", "群主", "value", "群主是 C", source_type="peer", source_id="u1")
    report = await backfill_facts(db)
    assert report["conflicts"] >= 1


def test_source_kind_mapping() -> None:
    assert source_kind("peer", is_locked=True) == "operator"
    assert source_kind("owner", is_locked=False) == "operator"
    assert source_kind("system", is_locked=False) == "system"
    assert source_kind("weird", is_locked=False) == "peer"


async def test_claim_store_has_tag(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "tag.db")
    await db.initialize()
    store = SqliteClaimStore(db)
    await store.assert_claim("g", "s", "value", "v", tag="t1")
    assert await store.has_tag("t1") and not await store.has_tag("nope")
