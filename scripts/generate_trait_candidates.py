#!/usr/bin/env python
"""Generate offline trait candidates from evidence (shadow; never edits prompt)."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_candidate_repo import SqliteTraitCandidateStore
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.core.config import load_config_from_json
from echomind.mind.trait_generation import TraitTextGenerator

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--config", type=Path, default=ROOT / "data" / "config.json")
    parser.add_argument("--trait-id", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SqliteDatabase(args.db)
    await db.initialize()
    query = (
        "SELECT id, category, trait_text FROM persona_traits "
        "WHERE status='active' AND id=? ORDER BY id"
        if args.trait_id else
        "SELECT id, category, trait_text FROM persona_traits "
        "WHERE status='active' ORDER BY id"
    )
    params = (args.trait_id,) if args.trait_id else ()
    async with db.connect() as conn:
        rows = list(await (await conn.execute(query, params)).fetchall())
    if not rows:
        print("no active traits; P1 shadow has not activated any trait yet")
        return 0

    evidence_store = SqliteTraitEvidenceStore(db)
    if args.dry_run:
        for trait_id, category, text in rows:
            evidence = await evidence_store.list_trait_evidence(int(trait_id), 200)
            contexts = {item.context_hash for item in evidence}
            print(f"{trait_id} {category} contexts={len(contexts)} {text[:40]}")
        return 0

    cfg = load_config_from_json(args.config)
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    generator = TraitTextGenerator(llm, cfg.primary_llm.model)
    store = SqliteTraitCandidateStore(db)
    for trait_id, _category, _text in rows:
        evidence = await evidence_store.list_trait_evidence(int(trait_id), 200)
        candidate = await generator.generate(int(trait_id), evidence)
        if candidate is None:
            continue
        await store.save_candidate(candidate)
        print(f"{trait_id} {candidate.status} {candidate.trait_text[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
