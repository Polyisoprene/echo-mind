#!/usr/bin/env python
"""Shadow audit: what active traits would allow, without changing behavior."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.domain.models import PersonaTrait
from echomind.mind.trait_action_eligibility import evaluate_eligibility

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    await db.initialize()
    async with db.connect() as conn:
        rows = await (await conn.execute(
            "SELECT id, category, trait_text FROM persona_traits WHERE status='active'"
        )).fetchall()
    if not rows:
        print("no active traits; shadow eligibility is empty")
        return 0
    evidence_store = SqliteTraitEvidenceStore(db)
    traits: list[PersonaTrait] = []
    evidence = {}
    for trait_id, category, text in rows:
        trait = PersonaTrait(
            trait_id=int(trait_id), category=category, trait_text=str(text),
        )
        traits.append(trait)
        evidence[trait.trait_id] = await evidence_store.list_trait_evidence(
            trait.trait_id, 200
        )
    result = evaluate_eligibility(tuple(traits), evidence)
    print(f"allowed_tools={sorted(result.allowed_tools)}")
    print(f"allow_refusal={result.allow_refusal}")
    for reason in result.reasons:
        print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
