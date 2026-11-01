"""B4: the claim read path carries provenance and applies the privacy gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.adapters.storage.claim_repo import SqliteClaimStore
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository


async def test_facts_v2_reads_claims_with_privacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FACTS_V2", "on")
    db = SqliteDatabase(tmp_path / "claims.db")
    await db.initialize()
    store = SqliteClaimStore(db)
    await store.assert_claim(
        "g", "公开", "value", "群规", source_type="system",
        scope="venue", sensitivity="group", source_turn_id="t1",
    )
    await store.assert_claim(
        "g", "秘密", "value", "暗号", source_type="system",
        scope="person", owner_id="L", sensitivity="secret",
    )
    facts = await SqliteMemoryRepository(db).get_semantic_facts("g")
    assert [fact.subject for fact in facts] == ["公开"]
    assert facts[0].source_turn_id == "t1"
