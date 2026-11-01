"""P0: trait evidence ledger must be append-only and deduplicated per turn."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import PersonaTrait, TurnOutcome
from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.plasticity import NeuroplasticityEngine


async def test_evidence_roundtrip_and_turn_dedupe(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "trait_evidence.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    evidence_store = SqliteTraitEvidenceStore(db)
    traits = await store.sync_persona_traits(
        new_trait=PersonaTrait(trait_text="看到图会先看细节", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = next(item for item in traits if item.trait_text == "看到图会先看细节")
    row = TraitEvidence(
        trait_id=trait.trait_id, session_id="s1", turn_id="t1",
        quote="这张图的细节好多", quote_kind="assistant", polarity=1,
        context_hash="c1", created_ms=1,
    )
    await evidence_store.record_trait_evidence(row)
    await evidence_store.record_trait_evidence(row.model_copy(update={"session_id": "s2"}))
    rows = await evidence_store.list_trait_evidence(trait.trait_id)
    assert len(rows) == 1
    assert rows[0].quote == "这张图的细节好多"
    assert rows[0].context_hash == "c1"


async def test_turn_outcome_writes_evidence(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "trait_evidence_wire.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    evidence_store = SqliteTraitEvidenceStore(db)
    engine = NeuroplasticityEngine(store, evidence_store=evidence_store)
    outcome = TurnOutcome(
        session_id="turn-42", chat_key="group:1", triggers=(),
        sent_texts=("我看到图里那个小槽点了",), tools_used=("look_at_image",),
        social_reward=0.8,
    )
    await engine._learn_traits(outcome)  # noqa: SLF001 - direct unit of the write path
    traits = await store.sync_persona_traits()
    target = next(t for t in traits if "看到群友发图" in t.trait_text)
    rows = await evidence_store.list_trait_evidence(target.trait_id)
    assert rows and rows[0].quote_kind == "assistant"
    assert rows[0].turn_id == "turn-42"


async def test_lifecycle_refresh_is_shadow_only(tmp_path: Path) -> None:
    import sqlite3

    db = SqliteDatabase(tmp_path / "trait_lifecycle.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    evidence_store = SqliteTraitEvidenceStore(db)
    traits = await store.sync_persona_traits(
        new_trait=PersonaTrait(trait_text="会先看画面细节", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = next(item for item in traits if item.trait_text == "会先看画面细节")
    for index, context in enumerate(("c1", "c2"), 1):
        await evidence_store.record_trait_evidence(TraitEvidence(
            trait_id=trait.trait_id, session_id=f"s{index}", turn_id=f"t{index}",
            quote="细节", quote_kind="assistant", polarity=1,
            context_hash=context, created_ms=index,
        ))
    assert await evidence_store.refresh_lifecycle(trait.trait_id) == "active"
    for index, context in enumerate(("c3", "c4"), 3):
        await evidence_store.record_trait_evidence(TraitEvidence(
            trait_id=trait.trait_id, session_id=f"s{index}", turn_id=f"t{index}",
            quote="不是这样", quote_kind="user", polarity=-1,
            context_hash=context, created_ms=index,
        ))
    assert await evidence_store.refresh_lifecycle(trait.trait_id) == "retired"
    con = sqlite3.connect(tmp_path / "trait_lifecycle.db")
    assert con.execute(
        "select status, last_support_ms, last_contradiction_ms, evidence_count, "
        "contradiction_count from persona_traits where id=?",
        (trait.trait_id,),
    ).fetchone() == ("retired", 2, 4, 2, 2)


async def test_candidate_store_dedupes_prompt_hash(tmp_path: Path) -> None:
    from echomind.adapters.storage.trait_candidate_repo import SqliteTraitCandidateStore
    from echomind.domain.trait_candidate import TraitCandidate

    db = SqliteDatabase(tmp_path / "trait_candidates.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    traits = await store.sync_persona_traits(
        new_trait=PersonaTrait(trait_text="候选测试", strength=5),
        chat_key="g", source="turn:t1",
    )
    trait = next(item for item in traits if item.trait_text == "候选测试")
    candidate = TraitCandidate(
        trait_id=trait.trait_id, category="habit", trait_text="看到图会先看细节",
        evidence_json="[]", prompt_hash="hash-1", generator_model="test",
        created_ms=1,
    )
    candidates = SqliteTraitCandidateStore(db)
    await candidates.save_candidate(candidate)
    await candidates.save_candidate(candidate)
    assert len(await candidates.list_candidates(trait.trait_id)) == 1


async def test_candidate_promotion_is_explicit_and_audited(tmp_path: Path) -> None:
    from echomind.adapters.storage.trait_candidate_repo import SqliteTraitCandidateStore
    from echomind.domain.trait_candidate import TraitCandidate

    db = SqliteDatabase(tmp_path / "promotion.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    traits = await store.sync_persona_traits(
        new_trait=PersonaTrait(trait_text="晋升测试", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = next(item for item in traits if item.trait_text == "晋升测试")
    candidates = SqliteTraitCandidateStore(db)
    candidate = TraitCandidate(
        trait_id=trait.trait_id, category="habit", trait_text="会先看细节",
        evidence_json="[]", prompt_hash="promote-1", created_ms=1,
    )
    await candidates.save_candidate(candidate)
    saved = (await candidates.list_candidates(trait.trait_id))[0]
    assert await candidates.promote_candidate(saved.candidate_id, "operator", "reviewed") is True
    promoted = await candidates.get_candidate(saved.candidate_id)
    assert promoted is not None and promoted.status == "promoted"
    assert promoted.promote_reason == "reviewed"
    assert await candidates.promote_candidate(saved.candidate_id, "operator", "again") is False


async def test_included_memory_ids_create_causal_links(tmp_path: Path) -> None:
    from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore

    db = SqliteDatabase(tmp_path / "causal_links.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    evidence_store = SqliteTraitEvidenceStore(db)
    links = SqliteTraitMemoryLinkStore(db)
    engine = NeuroplasticityEngine(
        store, evidence_store=evidence_store, trait_links=links,
    )
    outcome = TurnOutcome(
        session_id="turn-causal", chat_key="g", triggers=(),
        sent_texts=("这张图里有小槽点",), tools_used=("look_at_image",),
        social_reward=0.8,
    )
    await engine._learn_traits(outcome, memory_ids=(7,))  # noqa: SLF001
    traits = await store.sync_persona_traits()
    trait = next(item for item in traits if "看到群友发图" in item.trait_text)
    rows = await links.list_links(trait.trait_id)
    assert len(rows) == 1 and rows[0].memory_id == 7
    assert rows[0].is_context is True
    second = outcome.model_copy(update={"session_id": "turn-causal-2"})
    await engine._learn_traits(second, memory_ids=(7,))  # noqa: SLF001
    assert len(await links.list_links(trait.trait_id)) == 1


async def test_trait_learning_runs_without_param_deltas(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "no_deltas.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    evidence = SqliteTraitEvidenceStore(db)
    engine = NeuroplasticityEngine(store, evidence_store=evidence)
    outcome = TurnOutcome(
        session_id="neutral-turn", chat_key="g", triggers=(),
        sent_texts=("记一下这个小习惯",), tools_used=("feiyu_say",),
        social_reward=0.0,
    )
    await engine.adapt_from_outcome(outcome)
    traits = await store.sync_persona_traits()
    target = next(item for item in traits if "发语音" in item.trait_text)
    rows = await evidence.list_trait_evidence(target.trait_id)
    assert len(rows) == 1 and rows[0].turn_id == "neutral-turn"
