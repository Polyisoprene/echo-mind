#!/usr/bin/env python
"""P6e persona evaluation harness (offline by default).

Suites:
  stability  — drive the two-layer engine for N simulated days and report drift;
  affect     — scripted appraisals, check the *direction* of each emotional change;
  recall     — seed facts, query them directly and by paraphrase, report Recall@k;
  sensitivity— requires `--live-llm`: does a persona dimension change the output?

Offline suites are deterministic (fixed clock, no network) and CI-safe.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.storage.database import SqliteDatabase  # noqa: E402
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository  # noqa: E402
from echomind.adapters.storage.persona_layer_repo import SqlitePersonaLayerStore  # noqa: E402
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore  # noqa: E402
from echomind.domain.models import (  # noqa: E402
    AffectiveVector,
    Percept,
    SemanticFact,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.mind.drives import apply_turn_affect_and_drives  # noqa: E402
from echomind.mind.persona_dynamics import TRAIT_ANNUAL_BUDGET  # noqa: E402
from echomind.mind.plasticity import NeuroplasticityEngine  # noqa: E402
from echomind.mind.ranker_fusion import unified_rank  # noqa: E402
from echomind.mind.subconscious_probe import SubconsciousChordResult  # noqa: E402

DAY_MS = 86_400_000
CLOCK = 1_770_000_000_000
RECALL_K = 8

# 16 facts with a direct and a paraphrase query each. Paraphrases deliberately
# avoid the fact's wording where possible, which is exactly where lexical recall
# is expected to fail — the point of the baseline.
FACTS: tuple[tuple[str, str, str, str], ...] = (
    ("小明", "小明最喜欢草莓蛋糕", "小明喜欢吃什么", "甜品里最爱的是哪一款"),
    ("小红", "小红住在杭州", "小红住在哪里", "现在定居在哪个城市"),
    ("阿杰", "阿杰养了一只布偶猫", "阿杰养了什么", "家里那只宠物是什么品种"),
    ("老张", "老张在字节跳动上班", "老张在哪上班", "他在哪家公司工作"),
    ("小美", "小美会弹钢琴", "小美会什么乐器", "音乐方面有什么特长"),
    ("大刘", "大刘刚买了一辆特斯拉", "大刘买了什么车", "他最近提了什么新车"),
    ("阿强", "阿强讨厌香菜", "阿强讨厌什么", "最受不了哪种配菜"),
    ("小周", "小周每天跑步五公里", "小周每天跑多少", "有什么运动习惯"),
    ("老王", "老王是群主", "谁是群主", "群里谁说了算"),
    ("小林", "小林在准备考研", "小林在准备什么", "最近在忙什么事情"),
    ("阿珍", "阿珍喜欢看恐怖片", "阿珍喜欢看什么电影", "她偏爱哪种类型的影片"),
    ("小陈", "小陈生日是三月七号", "小陈生日是哪天", "他什么时候过生日"),
    ("阿豪", "阿豪打游戏很厉害", "阿豪游戏水平怎么样", "他玩得好不好"),
    ("小雅", "小雅养了两只柯基", "小雅养了几只狗", "她家有几只小短腿"),
    ("老李", "老李会做川菜", "老李会做什么菜", "他的厨艺擅长哪个菜系"),
    ("阿敏", "阿敏在学日语", "阿敏在学什么外语", "她最近在学哪门语言"),
)


async def suite_stability(days: int) -> dict[str, Any]:
    """Simulate `days` of maximal positive evidence and report baseline drift."""
    workdir = Path(tempfile.mkdtemp(prefix="echomind-eval-"))
    db = SqliteDatabase(workdir / "eval.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    await store.ensure_default_params()
    layers = await SqlitePersonaLayerStore.open(db)
    engine = NeuroplasticityEngine(store, layers)

    start = (await store.get_plastic_params())["persona_warmth"].value
    for day in range(days):
        await layers.record_observation("persona_warmth", 50.0, CLOCK + day * DAY_MS)
        await engine.settle_baseline(CLOCK + (day + 1) * DAY_MS)
    end = (await store.get_plastic_params())["persona_warmth"].value
    one_year = TRAIT_ANNUAL_BUDGET * days / 365.0
    return {
        "status": "ok",
        "days": days,
        "baseline_start": round(start, 4),
        "baseline_end": round(end, 4),
        "net_change": round(end - start, 4),
        "expected_one_year_budget": TRAIT_ANNUAL_BUDGET,
        "scaled_budget": round(one_year, 4),
        "saturated": end >= 97.999,
    }


def _snapshot() -> WorkingSnapshot:
    """Start at the affect set point so the appraisal effect is not swamped by the pull."""
    return WorkingSnapshot(
        scope_key="global",
        affect=AffectiveVector(
            valence=62.0, energy=75.0, jealousy=0.0, shyness=20.0, irritation=0.0
        ),
    )


def _bond() -> SocialBondProfile:
    return SocialBondProfile(
        chat_key="g", user_id="u", user_name="u",
        affinity_score=80.0, trust_score=0.9, bond_depth=50.0,
    )


def _percept() -> Percept:
    return Percept(
        chat_key="g", scene="group", message_id="m", timestamp_ms=CLOCK,
        sender_id="u", sender_name="u", text="hi",
    )


def _delta(chord: SubconsciousChordResult) -> Any:
    return apply_turn_affect_and_drives(
        _snapshot(), (_percept(),), (), bonds_map={"u": _bond()}, chord=chord
    )


def suite_affect() -> dict[str, Any]:
    """Check that scripted appraisals move the affect in the expected direction."""
    base = _snapshot()
    cases = (
        ("joy", SubconsciousChordResult(joy=3), "valence", 1),
        ("hurt", SubconsciousChordResult(hurt=3), "valence", -1),
        ("annoyance", SubconsciousChordResult(annoyance=3), "irritation", 1),
        ("jealousy", SubconsciousChordResult(jealousy=3), "jealousy", 1),
        ("neutral", SubconsciousChordResult(), "valence", 0),
    )
    results: list[dict[str, Any]] = []
    for name, chord, field, expected in cases:
        after = _delta(chord)
        before_value = getattr(base.affect, field)
        after_value = getattr(after.affect, field)
        delta = after_value - before_value
        sign = 0 if abs(delta) < 0.05 else (1 if delta > 0 else -1)
        results.append(
            {
                "case": name,
                "field": field,
                "delta": round(delta, 2),
                "expected_sign": expected,
                "actual_sign": sign,
                "ok": sign == expected or (expected == 0 and abs(delta) < 1.0),
            }
        )
    hits = sum(1 for r in results if r["ok"])
    findings = [
        f"{r['case']}: {r['field']} moved {r['delta']:+} but expected sign "
        f"{r['expected_sign']}"
        for r in results
        if not r["ok"]
    ]
    return {
        "status": "ok",
        "cases": results,
        "accuracy": round(hits / len(results), 3),
        "findings": findings,
    }


async def suite_recall() -> dict[str, Any]:
    """Seed facts into a temp DB and measure recall for direct vs paraphrased queries."""
    workdir = Path(tempfile.mkdtemp(prefix="echomind-recall-"))
    db = SqliteDatabase(workdir / "memory.db")
    await db.initialize()
    repo = SqliteMemoryRepository(db)
    for subject, text, _direct, _para in FACTS:
        await repo.upsert_semantic_fact(
            SemanticFact(chat_key="g", subject=subject, fact_text=text, confidence=0.9,
                         source="system")
        )
    facts = await repo.get_semantic_facts("g")

    def hits(query: str, keyword: str) -> bool:
        picked = unified_rank(
            facts, query, {}, {}, 0,
            disabled=frozenset({"dense", "recency", "order", "relations", "confidence", "lock"}),
        )[:RECALL_K]
        return any(keyword in f.fact_text for f in picked)

    direct = [hits(_direct, text) for _subject, text, _direct, _para in FACTS]
    para = [hits(_para, text) for _subject, text, _direct, _para in FACTS]
    return {
        "status": "ok",
        "facts": len(facts),
        "k": RECALL_K,
        "direct_recall": round(sum(direct) / len(direct), 3),
        "paraphrase_recall": round(sum(para) / len(para), 3),
        "paraphrase_drop": round((sum(direct) - sum(para)) / len(FACTS), 3),
        "random_baseline": round(RECALL_K / len(facts), 3),
    }


def suite_sensitivity(live: bool) -> dict[str, Any]:
    """Live-only: does a persona dimension change the generated output?"""
    if not live:
        return {
            "status": "not_run",
            "reason": "requires --live-llm; offline suites must stay free and deterministic",
            "protocol": {
                "scenarios": 24,
                "levels": ["p10", "baseline", "p90"],
                "generations": 7 * 2 * 24,
                "metrics": ["pairwise_judge_accuracy", "feature_direction", "self_consistency"],
                "pass": "Wilson lower bound > 0.5 for >=5 of 7 dimensions",
            },
        }
    return {
        "status": "not_implemented",
        "reason": "run scripts/persona_sensitivity.py --dry-run, then --scenarios 4",
    }


def _git_head() -> str:
    try:
        return subprocess.run(  # noqa: S603, S607 - fixed argv, no shell
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 - fixed argv
            cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout.strip()
    except OSError:
        return ""


async def run(suites: tuple[str, ...], days: int, live: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "git_head": _git_head(),
        "clock": CLOCK,
        "suites": {},
    }
    if "stability" in suites:
        report["suites"]["stability"] = await suite_stability(days)
    if "affect" in suites:
        report["suites"]["affect"] = suite_affect()
    if "recall" in suites:
        report["suites"]["recall"] = await suite_recall()
    if "sensitivity" in suites:
        report["suites"]["sensitivity"] = suite_sensitivity(live)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="all",
                        choices=["all", "stability", "affect", "recall", "sensitivity"])
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    parser.add_argument("--live-llm", action="store_true")
    args = parser.parse_args()

    suites = (
        ("stability", "affect", "recall", "sensitivity")
        if args.suite == "all"
        else (args.suite,)
    )
    report = asyncio.run(run(suites, args.days, args.live_llm))
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = args.out / f"persona_eval_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {name: {k: v for k, v in data.items() if k not in ("cases", "protocol")}
               for name, data in report["suites"].items()}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
