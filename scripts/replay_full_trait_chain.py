#!/usr/bin/env python
"""Offline full chain: replay → active trait → real candidate → review → promote → prompt diff."""

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
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.core.config import load_config_from_json
from echomind.mind.trait_generation import TraitTextGenerator
from echomind.mind.trait_promotion import review_candidate
from echomind.mind.trait_prompt_shadow import build_shadow_prompts

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=("warm", "offense", "mixed"), default="warm")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--approve-promotion", action="store_true")
    parser.add_argument("--reason", default="offline replay benchmark")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="echo-full-chain-"))
    db_path = workdir / "chain.db"
    replay = await run_stream(args.stream, args.days, db_path)
    db = SqliteDatabase(db_path)
    await db.initialize()
    active = await SqliteTraitShadowStore(db).active_traits()
    if not active:
        print("no active traits")
        return 0
    trait = active[0]
    evidence_store = SqliteTraitEvidenceStore(db)
    evidence = await evidence_store.list_trait_evidence(trait.trait_id, 200)
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    candidate = await TraitTextGenerator(llm, cfg.primary_llm.model).generate(
        trait.trait_id, evidence
    )
    if candidate is None:
        print("candidate generation skipped")
        return 0
    candidates = SqliteTraitCandidateStore(db)
    await candidates.save_candidate(candidate)
    saved = (await candidates.list_candidates(trait.trait_id))[0]
    review = review_candidate(saved, evidence)
    promoted = False
    if args.approve_promotion and review.eligible:
        promoted = await candidates.promote_candidate(
            saved.candidate_id, "benchmark-operator", args.reason
        )
    shadow = None
    if promoted:
        working = SqliteWorkingStateStore(db)
        traits = await working.sync_persona_traits()
        shadow = build_shadow_prompts(
            await working.get_plastic_params(), traits, saved
        )
    report: dict[str, Any] = {
        "stream": args.stream,
        "days": args.days,
        "replay": replay,
        "candidate": {
            "status": saved.status,
            "text": saved.trait_text,
            "review_eligible": review.eligible,
            "review_reasons": list(review.reasons),
        },
        "promotion": {
            "requested": args.approve_promotion,
            "promoted": promoted,
            "reason": args.reason if promoted else "",
        },
        "prompt_shadow": None if shadow is None else {
            "old_len": shadow.old_len,
            "new_len": shadow.new_len,
            "delta": shadow.len_delta,
            "candidate_in_old": saved.trait_text in shadow.old,
            "candidate_in_new": saved.trait_text in shadow.new,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
