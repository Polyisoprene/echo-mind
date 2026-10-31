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
