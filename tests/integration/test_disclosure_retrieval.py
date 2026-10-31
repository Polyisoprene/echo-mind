"""P3: private facts stay in their venue or the owner's private chat; secret never surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_private_fact_respects_venue_and_owner(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "gate.db")
    repo = container.memory_repo
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="L的病", fact_text="最近在休养",
                     scope="person", owner_id="L", sensitivity="private")
    )
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="暗号", fact_text="只告诉过你",
                     scope="venue", owner_id="L", sensitivity="secret")
    )

    group1 = {f.subject for f in await repo.get_semantic_facts("group:1")}
    group2 = {f.subject for f in await repo.get_semantic_facts("group:2")}
    private = {f.subject for f in await repo.get_semantic_facts("private:L")}

    assert "L的病" in group1, "the source venue may recall a private fact"
    assert "L的病" not in group2, "another venue must not"
    assert "L的病" in private, "the owner's private chat may recall it"
    assert "暗号" not in group1 | group2 | private, "secret is denied until a grant exists"


@pytest.mark.asyncio
async def test_private_fact_gate_and_log_end_to_end(tmp_path: Path) -> None:
    import sqlite3

    from echomind.adapters.storage.disclosure_repo import SqliteDisclosureLog
    from echomind.mind.facade_memory import gate_frame

    db_path = tmp_path / "e2e.db"
    container = await EchoMindContainer.create(db_path=db_path)
    repo = container.memory_repo
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="L的病", fact_text="最近在休养",
                     scope="person", owner_id="L", sensitivity="private")
    )
    stored = next(f for f in await repo.get_semantic_facts("group:1")
                  if f.subject == "L的病")
    log = SqliteDisclosureLog(container.db)

    kept, _ = await gate_frame((stored,), (), frozenset({"M"}), "group:1", log)
    assert kept == ()
    kept, _ = await gate_frame((stored,), (), frozenset({"L"}), "group:1", log)
    assert len(kept) == 1

    rows = sqlite3.connect(db_path).execute(
        "SELECT action, reason FROM disclosures ORDER BY id"
    ).fetchall()
    assert ("keep", "owner_absent") in rows
    assert ("say", "persona") in rows
