"""P3 end-to-end: experience -> evidence -> active trait -> linked memory → rank."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_quote_lookup import SqliteMemoryQuoteLookup
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import Percept, SemanticFact, TurnOutcome
from echomind.mind.plasticity import NeuroplasticityEngine
from echomind.mind.ranker_fusion import unified_rank
from echomind.mind.trait_memory_linker import link_exact_quotes

DAY = 86_400_000
ALL = frozenset({
    "bm25", "dense", "recency", "order", "relations", "confidence", "lock", "trait",
})


def _outcome(day: int, quote: str) -> TurnOutcome:
    percept = Percept(
        chat_key="g", scene="group", message_id=f"m{day}", timestamp_ms=day * DAY,
        sender_id="u1", sender_name="U", text="发图",
    )
    return TurnOutcome(
        session_id=f"turn-{day}", chat_key="g", triggers=(percept,),
        sent_texts=(quote,), tools_used=("look_at_image",), social_reward=0.8,
    )


async def test_experience_to_trait_to_memory_rank(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "evolution_loop.db")
    await db.initialize()
    working = SqliteWorkingStateStore(db)
    evidence_store = SqliteTraitEvidenceStore(db)
    engine = NeuroplasticityEngine(working, evidence_store=evidence_store)

    quote = "我看到图里那个小槽点了"
    await engine._learn_traits(_outcome(1, quote))  # noqa: SLF001
    await engine._learn_traits(_outcome(2, quote))  # noqa: SLF001
    traits = await working.sync_persona_traits()
    trait = next(item for item in traits if "看到群友发图" in item.trait_text)
    evidence = await evidence_store.list_trait_evidence(trait.trait_id)
    assert len({item.context_hash for item in evidence}) == 2
    assert await evidence_store.refresh_lifecycle(trait.trait_id) == "active"

    repo = SqliteMemoryRepository(db)
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="看图", fact_text="看到图会先找小槽点",
        source_quote=quote,
    ))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="g", subject="天气", fact_text="今天天气不错",
    ))
    facts = await repo.get_semantic_facts("g")
    target = next(fact for fact in facts if "小槽点" in fact.fact_text)

    links = SqliteTraitMemoryLinkStore(db)
    result = await link_exact_quotes(
        trait.trait_id, "g", evidence, SqliteMemoryQuoteLookup(db), links,
    )
    assert result.semantic == 1
    scores = await links.ranker_scores((trait.trait_id,))
    ranked = unified_rank(
        facts, "她看到图会做什么", {}, {}, 3 * DAY,
        disabled=ALL - {"trait"}, trait_scores=scores,
    )
    assert ranked[0].fact_id == target.fact_id
