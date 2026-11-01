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


def test_prompt_can_filter_traits_by_evidence() -> None:
    from echomind.mind.personality import synthesize_live_persona_directive

    old = PersonaTrait(category="habit", trait_text="只出现一次的习惯", evidence_count=1,
                       status="candidate")
    stable = PersonaTrait(category="habit", trait_text="反复出现的习惯", evidence_count=3,
                          status="active")
    text = synthesize_live_persona_directive(
        {}, (old, stable), min_evidence=2, max_traits=6
    )
    assert "反复出现的习惯" in text
    assert "只出现一次的习惯" not in text
