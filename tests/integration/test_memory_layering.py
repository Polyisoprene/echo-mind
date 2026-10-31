"""P2.2: person facts cross venues, venue facts stay local, global facts stay visible."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_person_facts_follow_the_person_not_the_room(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "layers.db")
    repo = container.memory_repo
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="L", fact_text="喜欢猫",
                     scope="person", owner_id="L", sensitivity="private")
    )
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="群规", fact_text="周五团建", scope="venue")
    )
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="global", subject="新闻", fact_text="今天下雨",
                     scope="global", sensitivity="public")
    )

    private = {f.subject for f in await repo.get_semantic_facts("private:L", person_ids=("L",))}
    assert "L" in private, "person facts must cross venues"
    assert "群规" not in private, "venue facts must stay local"
    assert "新闻" in private, "global facts remain visible"

    plain = {f.subject for f in await repo.get_semantic_facts("group:2")}
    assert "L" not in plain, "without person_ids, a person fact is not recalled elsewhere"

    group = {f.subject for f in await repo.get_semantic_facts("group:1")}
    assert "群规" in group
