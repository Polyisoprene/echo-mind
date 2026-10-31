"""P3.3: the write path enforces cue-based sensitivity and the gate honours it."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_secret_cue_is_stored_and_never_recalled(tmp_path: Path) -> None:
    db_path = tmp_path / "sens.db"
    container = await EchoMindContainer.create(db_path=db_path)
    repo = container.memory_repo
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="病", fact_text="别告诉别人，我在休养",
                     source_person_id="L")
    )
    raw = sqlite3.connect(db_path).execute(
        "SELECT sensitivity, owner_id FROM semantic_facts WHERE subject='病'"
    ).fetchone()
    assert raw == ("secret", "L")
    assert not any(f.subject == "病" for f in await repo.get_semantic_facts("group:1"))
    assert not any(f.subject == "病" for f in await repo.get_semantic_facts("private:L"))


@pytest.mark.asyncio
async def test_private_cue_stays_local(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "priv.db")
    repo = container.memory_repo
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="打算", fact_text="悄悄告诉你，我准备辞职",
                     source_person_id="L")
    )
    assert any(f.subject == "打算" for f in await repo.get_semantic_facts("group:1"))
    assert not any(f.subject == "打算" for f in await repo.get_semantic_facts("group:2"))
    assert not any(f.subject == "打算" for f in await repo.get_semantic_facts("private:L")), (
        "a venue-scoped fact stays in its venue; only person-scoped facts follow the owner"
    )
