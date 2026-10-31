#!/usr/bin/env python
"""Pilot: three sampled candidates vs one old trait, length-matched, paired."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from persona_replay import run_stream
from shadow_prompt_ab import (
    NEUTRAL_SPACE,
    _deltas,
    _reply,
    _scenarios,
)

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.core.config import load_config_from_json
from echomind.mind.trait_generation import TraitTextGenerator
from echomind.mind.trait_prompt_shadow import build_shadow_prompts

ROOT = Path(__file__).resolve().parents[1]


def _build_shadow(params: Any, traits: Any, candidate: Any) -> Any:
    base = build_shadow_prompts(params, traits, candidate)
    needed = base.old_len - base.new_len
    padded_text = candidate.trait_text + NEUTRAL_SPACE * max(0, needed)
    padded = candidate.model_copy(update={"trait_text": padded_text})
    shadow = build_shadow_prompts(params, traits, padded)
    if shadow.old_len != shadow.new_len:
        raise ValueError(f"length mismatch {shadow.old_len} != {shadow.new_len}")
    return shadow


def _unique_candidates(samples: list[Any]) -> list[Any]:
    unique: dict[str, Any] = {}
    for item in samples:
        if item is not None and item.status == "candidate":
            unique.setdefault(item.trait_text, item)
    return list(unique.values())


async def _old_replies(
    llm: FailoverLlmGateway, directive: str,
    scenarios: list[dict[str, str]], repeats: int,
) -> dict[tuple[str, int], str]:
    rows: dict[tuple[str, int], str] = {}
    for scenario in scenarios:
        for repeat in range(repeats):
            rows[(scenario["id"], repeat)] = await _reply(
                llm, directive, scenario["query"]
            )
    return rows


async def _candidate_result(
    llm: FailoverLlmGateway, shadow: Any, candidate: Any,
    scenarios: list[dict[str, str]], repeats: int,
    *, old_rows: dict[tuple[str, int], str],
) -> dict[str, Any]:
    by_scenario: list[tuple[list[str], list[str]]] = []
    for scenario in scenarios:
        olds, news = [], []
        for repeat in range(repeats):
            olds.append(old_rows[(scenario["id"], repeat)])
            news.append(await _reply(llm, shadow.new, scenario["query"]))
        by_scenario.append((olds, news))
    return {
        "text": candidate.trait_text, "old_len": shadow.old_len,
        "new_len": shadow.new_len, "paired_delta": _deltas(by_scenario),
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--candidates", type=int, default=3)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "eval" / "baselines" / "persona-multi-candidate-2026-11-01.json",
    )
    args = parser.parse_args()
    workdir = Path(tempfile.mkdtemp(prefix="echo-multi-candidate-"))
    db_path = workdir / "multi.db"
    await run_stream("warm", 30, db_path)
    db = SqliteDatabase(db_path)
    await db.initialize()
    active = await SqliteTraitShadowStore(db).active_traits()
    if not active:
        print("no active traits")
        return 0
    trait = active[0]
    evidence = await SqliteTraitEvidenceStore(db).list_trait_evidence(trait.trait_id, 200)
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    generator = TraitTextGenerator(llm, cfg.primary_llm.model, temperature=None)
    samples = [
        await generator.generate(trait.trait_id, evidence)
        for _ in range(args.candidates)
    ]
    candidates = _unique_candidates(samples)
    if not candidates:
        print("no valid candidates")
        return 0
    working = SqliteWorkingStateStore(db)
    params = await working.get_plastic_params()
    traits = await working.sync_persona_traits()
    shadows = [_build_shadow(params, traits, candidate) for candidate in candidates]
    scenarios = _scenarios(args.scenarios)
    old_rows = await _old_replies(llm, shadows[0].old, scenarios, args.repeats)
    results = [
        await _candidate_result(
            llm, shadow, candidate, scenarios, args.repeats, old_rows=old_rows
        )
        for candidate, shadow in zip(candidates, shadows, strict=True)
    ]
    report = {"n_scenarios": len(scenarios), "repeats": args.repeats,
              "n_candidates": len(candidates), "candidates": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
