#!/usr/bin/env python
"""Replay a stream to active traits, then generate one real LLM candidate each."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from persona_replay import run_stream

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_candidate_repo import SqliteTraitCandidateStore
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.core.config import load_config_from_json

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=("warm", "offense", "mixed"), default="warm")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="echo-replay-candidates-"))
    db_path = workdir / "replay.db"
    replay = await run_stream(args.stream, args.days, db_path)
    db = SqliteDatabase(db_path)
    await db.initialize()
    active = await SqliteTraitShadowStore(db).active_traits()
    if not active:
        print("no active traits after replay")
        return 0

    cfg = load_config_from_json(ROOT / "data" / "config.json")
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    from echomind.mind.trait_generation import TraitTextGenerator

    generator = TraitTextGenerator(llm, cfg.primary_llm.model)
    evidence_store = SqliteTraitEvidenceStore(db)
    candidates = SqliteTraitCandidateStore(db)
    results: list[dict[str, Any]] = []
    for trait in active:
        evidence = await evidence_store.list_trait_evidence(trait.trait_id, 200)
        candidate = await generator.generate(trait.trait_id, evidence)
        if candidate is not None:
            await candidates.save_candidate(candidate)
        results.append({
            "trait_id": trait.trait_id,
            "category": trait.category,
            "status": None if candidate is None else candidate.status,
            "trait_text": None if candidate is None else candidate.trait_text,
            "signature": None if candidate is None or candidate.signature is None
            else candidate.signature.model_dump(),
            "reject_reason": None if candidate is None else candidate.reject_reason,
        })
    report = {"replay": replay, "candidates": results}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
