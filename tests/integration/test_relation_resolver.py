"""P2: typed relations support a two-hop boost for fact retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.adapters.storage.relation_repo import SqliteRelationStore
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact
from echomind.domain.relation import MemoryRelation
from echomind.mind.relation_resolver import RelationResolver


@pytest.mark.asyncio
async def test_two_hop_reachable_and_boost(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "rel.db")
    store = SqliteRelationStore(container.db)
    await store.upsert(MemoryRelation(subject_id="a", predicate="friend", object_id="b"))
    await store.upsert(MemoryRelation(subject_id="b", predicate="works_at", object_id="x"))

    assert await store.reachable(("a",), 2) == {"a", "b", "x"}

    facts = (
        SemanticFact(fact_id=1, chat_key="g", subject="b", fact_text="b 在 x 工作"),
        SemanticFact(fact_id=2, chat_key="g", subject="z", fact_text="无关事实"),
    )
    boosted = await RelationResolver(store).boost_ids(facts, "a 的朋友在哪工作")
    assert boosted == {1}
