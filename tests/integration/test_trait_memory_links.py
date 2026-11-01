"""P3: trait-memory links are deduped and project to presence scores."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import PersonaTrait
from echomind.domain.trait_memory_link import TraitMemoryLink


async def test_link_roundtrip_and_ranker_scores(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "trait_memory.db")
    await db.initialize()
    traits = await SqliteWorkingStateStore(db).sync_persona_traits(
        new_trait=PersonaTrait(trait_text="会关心照顾类记忆", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = traits[0]
    store = SqliteTraitMemoryLinkStore(db)
    link = TraitMemoryLink(
        trait_id=trait.trait_id, memory_kind="semantic", memory_id=7,
        relation="supports", evidence_ms=1,
    )
    await store.link(link)
    await store.link(link)
    assert len(await store.list_links(trait.trait_id)) == 1
    assert await store.ranker_scores((trait.trait_id,)) == {7: 1.0}
    assert await store.ranker_scores((trait.trait_id,), "episodic") == {}


async def test_turn_support_links_only_same_turn_facts(tmp_path: Path) -> None:
    from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
    from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
    from echomind.domain.models import SemanticFact
    from echomind.domain.trait_evidence import TraitEvidence

    db = SqliteDatabase(tmp_path / "turn_support.db")
    await db.initialize()
    traits = await SqliteWorkingStateStore(db).sync_persona_traits(
        new_trait=PersonaTrait(trait_text="会记住同回合的事实", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = traits[0]
    await SqliteTraitEvidenceStore(db).record_trait_evidence(TraitEvidence(
        trait_id=trait.trait_id, session_id="t1", turn_id="t1", quote="事实",
        quote_kind="assistant", polarity=1, context_hash="c1", created_ms=1,
    ))
    repo = SqliteMemoryRepository(db)
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="某人", fact_text="同回合事实", source_turn_id="t1",
    ))
    fact_id = (await repo.get_semantic_facts("g"))[0].fact_id
    store = SqliteTraitMemoryLinkStore(db)
    assert await store.link_turn_support("g", "t1") == 1
    assert await store.link_turn_support("g", "other") == 0
    rows = await store.list_links(trait.trait_id)
    assert [(row.memory_id, row.is_context) for row in rows] == [(fact_id, False)]
    assert await store.ranker_scores((trait.trait_id,)) == {fact_id: 1.0}


async def test_manual_support_upgrades_context_with_note(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "manual.db")
    await db.initialize()
    traits = await SqliteWorkingStateStore(db).sync_persona_traits(
        new_trait=PersonaTrait(trait_text="手动确认", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = traits[0]
    store = SqliteTraitMemoryLinkStore(db)
    await store.link(TraitMemoryLink(
        trait_id=trait.trait_id, memory_kind="semantic", memory_id=7,
        is_context=True,
    ))
    await store.upsert_manual_support(
        trait.trait_id, 7, "手动确认：同回合语音行为", 123,
    )
    rows = await store.list_links(trait.trait_id)
    assert rows[0].is_context is False
    assert rows[0].note == "手动确认：同回合语音行为"
    assert await store.ranker_scores((trait.trait_id,)) == {7: 1.0}
