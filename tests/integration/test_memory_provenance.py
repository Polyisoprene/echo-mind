"""P2.1: facts and episodes persist their source, owner, sensitivity and audience."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import EpisodicCard, SemanticFact


@pytest.mark.asyncio
async def test_fact_provenance_roundtrip(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "prov.db")
    repo = container.memory_repo
    fact = SemanticFact(
        chat_key="group:1", subject="L", fact_text="喜欢猫", confidence=0.9,
        source="peer", scope="person", source_person_id="L", source_venue_id="group:1",
        owner_id="L", sensitivity="private", audience=("L", "bot"),
        source_quote="我其实喜欢猫",
    )
    ok, status = await repo.upsert_semantic_fact(fact)
    assert ok and status == "ok"

    stored = next(f for f in await repo.get_semantic_facts("group:1") if f.subject == "L")
    assert stored.scope == "person"
    assert stored.source_person_id == "L"
    assert stored.source_venue_id == "group:1"
    assert stored.owner_id == "L"
    assert stored.sensitivity == "private"
    assert stored.audience == ("L", "bot")
    assert stored.source_quote == "我其实喜欢猫"


@pytest.mark.asyncio
async def test_episode_provenance_roundtrip(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "prov2.db")
    repo = container.memory_repo
    card = EpisodicCard(
        chat_key="group:1", timestamp_ms=1_700_000_000_000, summary="在群里聊猫",
        key_detail="L 说他喜欢猫", participants=("L",), scope="venue",
        source_person_id="L", source_venue_id="group:1", owner_id="L",
        sensitivity="group", audience=("L",), source_quote="我其实喜欢猫",
    )
    card_id = await repo.save_episodic_card(card)
    assert card_id > 0

    stored = next(c for c in await repo.get_episodic_cards("group:1") if c.card_id == card_id)
    assert stored.source_person_id == "L"
    assert stored.source_venue_id == "group:1"
    assert stored.owner_id == "L"
    assert stored.sensitivity == "group"
    assert stored.audience == ("L",)
    assert stored.source_quote == "我其实喜欢猫"
