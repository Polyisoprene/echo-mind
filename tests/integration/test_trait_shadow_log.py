"""P4b: per-turn shadow log records eligibility without changing behavior."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import PersonaTrait, TurnOutcome
from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.trait_shadow_service import TraitShadowService


async def test_shadow_log_records_allowed_vs_actual_tools(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "shadow.db")
    await db.initialize()
    working = SqliteWorkingStateStore(db)
    traits = await working.sync_persona_traits(
        new_trait=PersonaTrait(category="taboo", trait_text="讨厌被命令", strength=7),
        chat_key="g", source="turn:t1",
    )
    trait = traits[0]
    evidence_store = SqliteTraitEvidenceStore(db)
    for index, context in enumerate(("c1", "c2"), 1):
        await evidence_store.record_trait_evidence(TraitEvidence(
            trait_id=trait.trait_id, session_id=f"s{index}", turn_id=f"t{index}",
            quote="look_at_image", quote_kind="tool", polarity=1,
            context_hash=context, created_ms=index,
        ))
    await evidence_store.refresh_lifecycle(trait.trait_id)
    store = SqliteTraitShadowStore(db)
    service = TraitShadowService(store, evidence_store, store)
    outcome = TurnOutcome(
        session_id="turn-9", chat_key="g", triggers=(),
        sent_texts=("不要这样命令我",), tools_used=("look_at_image",),
    )
    await service.record(outcome)
    rows = await store.list_shadow("g")
    assert len(rows) == 1
    assert rows[0].trait_ids == (trait.trait_id,)
    assert rows[0].allowed_tools == ("look_at_image",)
    assert rows[0].allow_refusal is True
    assert rows[0].actual_tools == ("look_at_image",)
