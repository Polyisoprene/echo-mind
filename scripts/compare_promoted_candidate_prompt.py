#!/usr/bin/env python
"""Render old vs promoted-candidate persona directives; never edits live."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_candidate_repo import SqliteTraitCandidateStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.mind.trait_prompt_shadow import build_shadow_prompts

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--candidate-id", type=int, required=True)
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    await db.initialize()
    candidate = await SqliteTraitCandidateStore(db).get_candidate(args.candidate_id)
    if candidate is None or candidate.status != "promoted":
        print("candidate must exist and be promoted")
        return 1
    working = SqliteWorkingStateStore(db)
    params = await working.get_plastic_params()
    traits = await working.sync_persona_traits()
    shadow = build_shadow_prompts(params, traits, candidate)
    print(f"old_len={shadow.old_len} new_len={shadow.new_len} delta={shadow.len_delta}")
    print(f"candidate_in_new={candidate.trait_text in shadow.new}")
    print(f"candidate_in_old={candidate.trait_text in shadow.old}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
