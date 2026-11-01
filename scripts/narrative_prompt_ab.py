#!/usr/bin/env python
"""Small shadow A/B: persona directive vs directive + evidence-bound narrative."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from shadow_prompt_ab import (
    REALISM_MAX_CHARS,
    _deltas,
    _run_replies,
    _scenarios,
)

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.core.config import load_config_from_json
from echomind.mind.narrative_identity import build_narrative
from echomind.mind.personality import synthesize_live_persona_directive
from echomind.mind.style_metrics import summarize
from echomind.mind.trait_prompt_shadow import PromptShadow

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--scenarios", type=int, default=6)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "eval" / "baselines" / "narrative-prompt-ab-2026-11-01.json",
    )
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    await db.initialize()
    active = await SqliteTraitShadowStore(db).active_traits()
    if not active:
        print("no active traits")
        return 0
    working = SqliteWorkingStateStore(db)
    params = await working.get_plastic_params()
    traits = await working.sync_persona_traits()
    narrative = await build_narrative(working, SqliteTraitEvidenceStore(db))
    if not narrative.lines:
        print("no narrative evidence")
        return 0
    old = synthesize_live_persona_directive(params, traits)
    new = old + "\n【自传式记忆】\n" + "\n".join(narrative.lines)
    shadow = PromptShadow(old=old, new=new)
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    rows, old_texts, new_texts, by_scenario = await _run_replies(
        llm, shadow, _scenarios(args.scenarios), args.repeats
    )
    report = {
        "narrative_lines": list(narrative.lines),
        "old_len": len(old), "new_len": len(new),
        "old_summary": summarize(old_texts, long_chars=REALISM_MAX_CHARS),
        "new_summary": summarize(new_texts, long_chars=REALISM_MAX_CHARS),
        "paired_delta": _deltas(by_scenario),
        "rows": rows,
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "old_len", "new_len", "old_summary", "new_summary", "paired_delta",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
