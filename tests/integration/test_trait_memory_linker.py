"""P3b: only exact source_quote matches become links."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_quote_lookup import SqliteMemoryQuoteLookup
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import EpisodicCard, PersonaTrait, SemanticFact
from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.trait_memory_linker import link_exact_quotes


def _evidence(quote: str, context: str, eid: int) -> TraitEvidence:
    return TraitEvidence(
        evidence_id=eid, trait_id=1, session_id=f"s{eid}", turn_id=f"t{eid}",
        quote=quote, quote_kind="assistant", polarity=1,
        context_hash=context, created_ms=eid,
    )


async def test_exact_quote_links_semantic_and_episodic(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "trait_links.db")
    await db.initialize()
    traits = await SqliteWorkingStateStore(db).sync_persona_traits(
        new_trait=PersonaTrait(trait_text="会关注猫图", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = traits[0]
    repo = SqliteMemoryRepository(db)
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="猫", fact_text="喜欢猫图", source_quote="喜欢猫图",
    ))
    await repo.save_episodic_card(EpisodicCard(
        chat_key="g", timestamp_ms=1, summary="看图", source_quote="看到猫图会停",
    ))
    lookup = SqliteMemoryQuoteLookup(db)
    links = SqliteTraitMemoryLinkStore(db)
    evidence = (
        _evidence("喜欢猫图", "c1", 1),
        _evidence("看到猫图会停", "c2", 2),
        _evidence("完全无关", "c3", 3),
    )
    dry = await link_exact_quotes(
        trait.trait_id, "g", evidence, lookup, links, dry_run=True,
    )
    assert dry.total == 2 and dry.skipped == 1
    assert await links.list_links(trait.trait_id) == ()
    result = await link_exact_quotes(trait.trait_id, "g", evidence, lookup, links)
    assert result.semantic == 1 and result.episodic == 1
    assert len(await links.list_links(trait.trait_id)) == 2
    assert len(await links.ranker_scores((trait.trait_id,))) == 1
