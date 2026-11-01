"""G1: structurally eligible candidates can be auto-promoted with an audit."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_auto_promotion import auto_promote
from echomind.adapters.storage.trait_candidate_repo import SqliteTraitCandidateStore
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import PersonaTrait
from echomind.domain.trait_candidate import TraitCandidate
from echomind.domain.trait_evidence import TraitEvidence


async def test_auto_promotion_requires_two_contexts(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "auto.db")
    await db.initialize()
    traits = await SqliteWorkingStateStore(db).sync_persona_traits(
        new_trait=PersonaTrait(trait_text="旧描述", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = traits[0]
    evidence = SqliteTraitEvidenceStore(db)
    for index, context in enumerate(("c1", "c2"), 1):
        await evidence.record_trait_evidence(TraitEvidence(
            trait_id=trait.trait_id, session_id=f"s{index}", turn_id=f"t{index}",
            quote="真实行为", quote_kind="assistant", polarity=1,
            context_hash=context, created_ms=index,
        ))
    candidate = TraitCandidate(
        trait_id=trait.trait_id, category="habit", trait_text="新描述",
        evidence_json="[]", prompt_hash="h", status="candidate", created_ms=1,
    )
    await SqliteTraitCandidateStore(db).save_candidate(candidate)
    results = await auto_promote(tmp_path / "auto.db", apply=True)
    assert results and results[0]["eligible"] is True
    con = con = __import__("sqlite3").connect(tmp_path / "auto.db")
    assert con.execute("SELECT trait_text, status FROM persona_traits").fetchone() == (
        "新描述", "active",
    )
    assert con.execute("SELECT status FROM trait_candidates").fetchone()[0] == "promoted"
