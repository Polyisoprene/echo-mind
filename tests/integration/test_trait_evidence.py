"""D15 step 1: every trait reinforcement records evidence, without changing prompts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import PersonaTrait


@pytest.mark.asyncio
async def test_reinforcement_increments_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "traits.db"
    container = await EchoMindContainer.create(db_path=db_path)
    trait = PersonaTrait(category="habit", trait_text="被摸头时会先嘴硬", strength=6)
    for _ in range(2):
        await container.working_store.sync_persona_traits(
            new_trait=trait, chat_key="group:1", source="turn:test"
        )
    row = sqlite3.connect(db_path).execute(
        "SELECT evidence_count, contradiction_count, last_evidence_ms, chat_key "
        "FROM persona_traits WHERE trait_text = ?",
        (trait.trait_text,),
    ).fetchone()
    assert row[0] == 2
    assert row[1] == 0
    assert row[2] > 0
    assert row[3] == "group:1"
