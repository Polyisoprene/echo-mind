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
