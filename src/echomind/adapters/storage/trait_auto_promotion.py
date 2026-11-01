"""G1 auto-promotion service: structural review is the only gate."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.domain.trait_candidate import TraitCandidate
from echomind.mind.trait_promotion import review_candidate


def _candidate(row: sqlite3.Row) -> TraitCandidate:
    return TraitCandidate(
        candidate_id=int(row["id"]), trait_id=int(row["trait_id"]),
        category=row["category"], trait_text=str(row["trait_text"]),
        evidence_json=str(row["evidence_json"]), prompt_hash=str(row["prompt_hash"]),
        generator_model=str(row["generator_model"]), status="candidate",
        created_ms=int(row["created_ms"]),
    )


async def auto_promote(db_path: Path, apply: bool) -> list[dict[str, object]]:
    db = SqliteDatabase(db_path)
    await db.initialize()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, trait_id, category, trait_text, evidence_json, prompt_hash, "
        "generator_model, status, created_ms FROM trait_candidates "
        "WHERE status='candidate' ORDER BY id"
    ).fetchall()
    evidence_store = SqliteTraitEvidenceStore(db)
    results: list[dict[str, object]] = []
    for row in rows:
        candidate = _candidate(row)
        evidence = await evidence_store.list_trait_evidence(candidate.trait_id, 100)
        review = review_candidate(candidate, evidence)
        result = {
            "candidate_id": candidate.candidate_id, "trait_id": candidate.trait_id,
            "eligible": review.eligible, "reasons": review.reasons,
        }
        if review.eligible and apply:
            now = int(time.time() * 1000)
            con.execute(
                "UPDATE trait_candidates SET status='promoted', promoted_by='auto-structural', "
                "promote_reason=?, promoted_ms=? WHERE id=? AND status='candidate'",
                ("auto: two independent contexts + behavioral quote", now, candidate.candidate_id),
            )
            con.execute(
                "UPDATE persona_traits SET trait_text=?, status='active' WHERE id=?",
                (candidate.trait_text, candidate.trait_id),
            )
            con.commit()
            result["applied"] = True
        results.append(result)
    con.close()
    return results

