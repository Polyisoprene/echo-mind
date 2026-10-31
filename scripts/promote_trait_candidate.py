#!/usr/bin/env python
"""Review/promote a candidate explicitly; promotion does not touch the prompt."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_candidate_repo import SqliteTraitCandidateStore
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.mind.trait_promotion import review_candidate

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    if args.approve and not args.reason.strip():
        print("refusing approval without --reason")
        return 2
    db = SqliteDatabase(args.db)
    await db.initialize()
    store = SqliteTraitCandidateStore(db)
    candidate = await store.get_candidate(args.candidate_id)
    if candidate is None:
        print("candidate not found")
        return 1
    evidence = await SqliteTraitEvidenceStore(db).list_trait_evidence(
        candidate.trait_id, 200
    )
    review = review_candidate(candidate, evidence)
    print(f"eligible={review.eligible} reasons={list(review.reasons)}")
    if not args.approve:
        return 0
    if not review.eligible:
        print("not promoted")
        return 1
    ok = await store.promote_candidate(args.candidate_id, "operator", args.reason.strip())
    print(f"promoted={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
