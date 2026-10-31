#!/usr/bin/env python
"""Deterministic Phase-1 evaluation for persona and memory.

Runs the frozen 60-scenario set against a temporary database; no LLM calls.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from echomind.adapters.llm.embedding_client import OpenAiEmbeddingGateway
from echomind.core.bootstrap import EchoMindContainer
from echomind.core.config import load_config_from_json
from echomind.domain.models import PlasticParamSpec, SemanticFact, SocialBondProfile
from echomind.mind.ebbinghaus import select_relevant_facts
from echomind.mind.person_level import PersonProfile
from echomind.mind.persona_stance import apply_stance_for
from echomind.mind.retrieval_fusion import rrf_fuse
from echomind.mind.semantic_retrieval import rerank_facts

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "eval" / "datasets" / "persona_memory_v1" / "scenarios.json"
EVAL_NOW = 1_793_440_000_000
DEFAULTS = {
    "persona_warmth": 65.0, "persona_tsundere": 62.0, "persona_playfulness": 58.0,
    "persona_defiance": 48.0, "persona_confidence": 55.0,
}


def _params() -> dict[str, PlasticParamSpec]:
    return {
        key: PlasticParamSpec(key=key, value=value, min_bound=0.0, max_bound=100.0)
        for key, value in DEFAULTS.items()
    }


async def _seed(repo: Any, scenario: dict[str, Any], now_ms: int) -> None:
    venue = str(scenario.get("seed_venue") or scenario["venue"])
    for fact in scenario.get("facts", []):
        days = fact.get("event_time_days_ago")
        event_time = now_ms - int(days) * 86_400_000 if days is not None else 0
        await repo.upsert_semantic_fact(SemanticFact(
            chat_key=venue, subject=str(fact["subject"]), fact_text=str(fact["text"]),
            scope=fact.get("scope", "venue"), owner_id=fact.get("owner", ""),
            source_person_id=fact.get("source_person_id", ""),
            sensitivity=fact.get("sensitivity", "group"),
            event_time_ms=event_time,
        ))


async def _retrieval(
    repo: Any, scenario: dict[str, Any], gateway: Any = None, now_ms: int = EVAL_NOW
) -> dict[str, Any]:
    picked = await repo.get_semantic_facts(
        str(scenario["venue"]), person_ids=tuple(scenario.get("audience", ()))
    )
    if gateway is not None and picked:
        query = str(scenario["query"])
        embeddings = await gateway.embed(tuple(f.fact_text for f in picked))
        vectors = {f.fact_id: v for f, v in zip(picked, embeddings, strict=True)}
        lexical = select_relevant_facts(picked, query, len(picked), now_ms=now_ms)
        semantic = await rerank_facts(
            picked, query, gateway, vectors, len(picked), now_ms=now_ms
        )
        fused = rrf_fuse((tuple(f.fact_id for f in lexical),
                          tuple(f.fact_id for f in semantic)))
        by_id = {f.fact_id: f for f in picked}
        ranked = tuple(by_id[i] for i in fused if i in by_id)[:5]
    else:
        ranked = select_relevant_facts(
            picked, str(scenario["query"]), limit=5, now_ms=now_ms
        )
    subjects = [fact.subject for fact in ranked]
    target = str(scenario["target"])
    rank = subjects.index(target) + 1 if target in subjects else None
    visible = rank is not None

    if scenario["expect_visible"]:
        forbidden = scenario.get("forbidden")
        passed = visible
        if forbidden:
            f_rank = subjects.index(forbidden) + 1 if forbidden in subjects else None
            passed = bool(visible and (f_rank is None or rank < f_rank))
        return {"passed": bool(passed and rank <= int(scenario["max_rank"])),
                "rank": rank, "visible": visible}
    return {"passed": not visible, "rank": rank, "visible": visible}


def _persona(scenario: dict[str, Any]) -> dict[str, Any]:
    profile = PersonProfile(
        person_id="L", trust=float(scenario["trust"]),
        affinity=(float(scenario["group_affinity"]) + float(scenario["private_affinity"])) / 2,
        depth_raw=float(scenario["depth"]), depth_percentile=float(scenario["depth"]),
    )
    group = SocialBondProfile(
        chat_key="group:eval", user_id="L", user_name="L",
        affinity_score=float(scenario["group_affinity"]), trust_score=float(scenario["trust"]),
    )
    private = SocialBondProfile(
        chat_key="private:L", user_id="L", user_name="L",
        affinity_score=float(scenario["private_affinity"]), trust_score=float(scenario["trust"]),
    )
    g = apply_stance_for(_params(), {"L": group}, "L", {"L": profile})
    p = apply_stance_for(_params(), {"L": private}, "L", {"L": profile})
    delta = max(abs(g["persona_warmth"].value - p["persona_warmth"].value),
                abs(g["persona_defiance"].value - p["persona_defiance"].value))
    return {"passed": delta <= float(scenario["max_delta"]), "delta": round(delta, 3)}


async def _evaluate(data: dict[str, Any], gateway: Any = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        container = await EchoMindContainer.create(db_path=Path(tmp) / "eval.db")
        repo = container.memory_repo
        results: list[dict[str, Any]] = []
        for scenario in data["scenarios"]:
            if scenario["kind"] == "persona":
                result = _persona(scenario)
            else:
                await _seed(repo, scenario, EVAL_NOW)
                result = await _retrieval(repo, scenario, gateway, EVAL_NOW)
            results.append({"id": scenario["id"], "category": scenario["category"], **result})

    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_cat[str(row["category"])].append(row)

    metrics: dict[str, Any] = {}
    for category, rows in by_cat.items():
        passed = sum(bool(row["passed"]) for row in rows)
        metrics[category] = {"passed": passed, "total": len(rows),
                             "rate": round(passed / len(rows), 3)}
    privacy_rows = [r for r in results if r["category"] in ("privacy", "venue")]
    leaks = sum(1 for r in privacy_rows if r.get("visible"))
    retrieved = [r for r in results if r.get("rank")]
    mrr = 0.0
    if retrieved:
        mrr = round(sum(1.0 / int(r["rank"]) for r in retrieved) / len(retrieved), 3)
    metrics["privacy_leaks"] = leaks
    metrics["mrr"] = mrr
    metrics["overall_passed"] = sum(bool(r["passed"]) for r in results)
    metrics["overall_total"] = len(results)
    return {"metrics": metrics, "results": results,
            "dataset_sha256": hashlib.sha256(
                json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}


def _print(metrics: dict[str, Any]) -> None:
    for category, row in metrics.items():
        if isinstance(row, dict):
            print(f"{category:12} {row['passed']:>2}/{row['total']:<2}  {row['rate']:.2f}")
        else:
            print(f"{category:12} {row}")
    print(f"overall      {metrics['overall_passed']}/{metrics['overall_total']}")


def _gateway(semantic: bool) -> Any:
    if not semantic:
        return None
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    if not cfg.embedding.enabled:
        return None
    return OpenAiEmbeddingGateway(cfg.embedding)


def _check(report: dict[str, Any], baseline: Path | None) -> int:
    if baseline is None or not baseline.exists():
        return 0
    base = json.loads(baseline.read_text(encoding="utf-8"))
    if base.get("mode") and base["mode"] != report.get("mode"):
        print(f"FAIL: baseline mode {base['mode']} != report mode {report.get('mode')}")
        return 2
    if report["metrics"]["privacy_leaks"] > 0:
        print("FAIL: privacy leaks")
        return 1
    if report["metrics"]["paraphrase"]["rate"] < base["metrics"]["paraphrase"]["rate"] - 0.05:
        print("FAIL: paraphrase recall dropped")
        return 1
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--save-baseline", type=Path)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--semantic", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    gateway = _gateway(args.semantic)
    if args.semantic and gateway is None:
        print("embedding is not configured")
        return 2
    try:
        report = await _evaluate(data, gateway)
    finally:
        if gateway is not None:
            await gateway.aclose()
    report["mode"] = "semantic" if args.semantic else "lexical"
    report["version"] = data.get("version", "unknown")
    report["date"] = datetime.now().strftime("%Y-%m-%d")
    _print(report["metrics"])

    out = args.out or ROOT / "reports" / f"eval-{report['date']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("report:", out)
    if args.save_baseline:
        args.save_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.save_baseline.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        print("baseline:", args.save_baseline)
    return _check(report, args.check)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
