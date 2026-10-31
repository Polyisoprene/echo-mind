#!/usr/bin/env python
"""Shadow A/B with repeated generations, paired deltas and bootstrap CI."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
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
from echomind.mind.style_metrics import summarize, text_flags
from echomind.mind.trait_generation import TraitTextGenerator
from echomind.mind.trait_promotion import review_candidate
from echomind.mind.trait_prompt_shadow import build_shadow_prompts

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "eval" / "datasets" / "persona_memory_v1" / "scenarios.json"
REALISM_MAX_CHARS = 26
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 42


def _scenarios(per_category: int) -> list[dict[str, str]]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    picked: list[dict[str, str]] = []
    for scenario in data["scenarios"]:
        category, query = scenario["category"], scenario.get("query", "")
        if not query or counts.get(category, 0) >= per_category:
            continue
        counts[category] = counts.get(category, 0) + 1
        picked.append({"id": scenario["id"], "category": category, "query": query})
    return picked


async def _reply(llm: FailoverLlmGateway, directive: str, query: str) -> str:
    response = await llm.complete([
        {"role": "system", "content": "你是 EchoMind。只输出你的回复，不要解释设定。"},
        {"role": "user", "content": f"{directive}\n\n【当前对话】\n用户：{query}"},
    ])
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    return str(message.get("content") or "").strip()


def _bootstrap_ci(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(BOOTSTRAP_SEED)  # noqa: S311 - deterministic bootstrap
    means = [
        sum(rng.choices(values, k=len(values))) / len(values)
        for _ in range(BOOTSTRAP_N)
    ]
    means.sort()
    return (round(means[int(0.025 * BOOTSTRAP_N)], 3),
            round(means[int(0.975 * BOOTSTRAP_N) - 1], 3))


def _deltas(old: list[str], new: list[str]) -> dict[str, dict[str, Any]]:
    fields = {
        "length": lambda text: float(len(text)),
        "long": lambda text: float(text_flags(text, REALISM_MAX_CHARS)["long"]),
        "explain": lambda text: float(text_flags(text, REALISM_MAX_CHARS)["explain"]),
        "roleplay": lambda text: float(text_flags(text, REALISM_MAX_CHARS)["roleplay"]),
        "multi_question": lambda text: float(
            text_flags(text, REALISM_MAX_CHARS)["multi_question"]
        ),
    }
    out: dict[str, dict[str, Any]] = {}
    for name, fn in fields.items():
        values = [fn(new_item) - fn(old_item) for old_item, new_item in zip(old, new, strict=True)]
        low, high = _bootstrap_ci(values)
        out[name] = {"mean": round(sum(values) / len(values), 3), "ci95": [low, high]}
    return out


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--per-category", type=int, default=2)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "eval" / "baselines" / "persona-prompt-ab-2026-11-01.json",
    )
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="echo-prompt-ab-"))
    db_path = workdir / "ab.db"
    await run_stream("warm", args.days, db_path)
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
    candidate = await TraitTextGenerator(llm, cfg.primary_llm.model).generate(
        trait.trait_id, evidence
    )
    if candidate is None:
        print("candidate generation skipped")
        return 0
    candidates = SqliteTraitCandidateStore(db)
    await candidates.save_candidate(candidate)
    saved = (await candidates.list_candidates(trait.trait_id))[0]
    if not review_candidate(saved, evidence).eligible:
        print("candidate failed structural review")
        return 0
    await candidates.promote_candidate(saved.candidate_id, "benchmark-operator", "shadow A/B")
    working = SqliteWorkingStateStore(db)
    shadow = build_shadow_prompts(
        await working.get_plastic_params(), await working.sync_persona_traits(), saved
    )
    rows: list[dict[str, Any]] = []
    old_texts: list[str] = []
    new_texts: list[str] = []
    for scenario in _scenarios(args.per_category):
        for repeat in range(args.repeats):
            old = await _reply(llm, shadow.old, scenario["query"])
            new = await _reply(llm, shadow.new, scenario["query"])
            old_texts.append(old)
            new_texts.append(new)
            rows.append({**scenario, "repeat": repeat, "old": old, "new": new})
    report = {
        "candidate": saved.trait_text,
        "old_directive_len": shadow.old_len,
        "new_directive_len": shadow.new_len,
        "n_pairs": len(rows),
        "old_summary": summarize(old_texts, long_chars=REALISM_MAX_CHARS),
        "new_summary": summarize(new_texts, long_chars=REALISM_MAX_CHARS),
        "paired_delta": _deltas(old_texts, new_texts),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {key: report[key] for key in ("n_pairs", "old_summary", "new_summary", "paired_delta")},
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
