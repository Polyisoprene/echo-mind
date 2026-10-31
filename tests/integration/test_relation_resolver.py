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
    boosted = await RelationResolver(store).boost_ids(facts, "a 的朋友在哪工作", 1_000)
    assert boosted == {1: 0.8}

    await store.upsert(MemoryRelation(subject_id="菲菲", predicate="lives_in", object_id="阿斋"))
    zh_fact = SemanticFact(fact_id=3, chat_key="g", subject="菲菲", fact_text="菲菲住在阿斋家")
    assert await RelationResolver(store).boost_ids((zh_fact,), "菲菲在哪", 1_000) == {3: 1.0}

    await store.upsert(MemoryRelation(
        subject_id="anchor", predicate="friend", object_id="old", valid_to_ms=500
    ))
    expired = SemanticFact(fact_id=4, chat_key="g", subject="old", fact_text="旧关系")
    assert await RelationResolver(store).boost_ids((expired,), "anchor 是谁", 1_000) == {}
