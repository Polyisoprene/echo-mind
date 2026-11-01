#!/usr/bin/env python
"""LongMemEval-S retrieval adapter (turn/session recall@5)."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from echomind.adapters.llm.embedding_client import OpenAiEmbeddingGateway
from echomind.core.config import load_config_from_json
from echomind.domain.models import SemanticFact
from echomind.mind.ranker_fusion import bm25_scores, unified_rank
from echomind.mind.semantic_retrieval import cosine

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "external" / "longmemeval_s.json"
DATE_RE = re.compile(r"(\\d{4})/(\\d{2})/(\\d{2})")


def _ms(value: str) -> int:
    match = DATE_RE.search(value)
    if not match:
        return 0
    year, month, day = (int(part) for part in match.groups())
    hour = minute = 0
    time_match = re.search(r"(\\d{2}):(\\d{2})", value)
    if time_match:
        hour, minute = (int(part) for part in time_match.groups())
    return int(datetime(year, month, day, hour, minute, tzinfo=UTC).timestamp() * 1000)


def _stratified(data: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in data:
        groups[str(item["question_type"])].append(item)
    selected: list[dict[str, Any]] = []
    for index in range(max(len(g) for g in groups.values())):
        for key in sorted(groups):
            if index < len(groups[key]) and len(selected) < limit:
                selected.append(groups[key][index])
    return selected


async def _embed_all(
    gateway: OpenAiEmbeddingGateway, texts: list[str], batch: int
) -> list[tuple[float, ...]]:
    vectors: list[tuple[float, ...]] = []
    for start in range(0, len(texts), batch):
        vectors.extend(await gateway.embed(tuple(texts[start:start + batch])))
    return vectors


def _facts(
    question: dict[str, Any], granularity: str = "session", max_chars: int = 6000,
) -> tuple[tuple[SemanticFact, ...], set[int]]:
    facts: list[SemanticFact] = []
    targets: set[int] = set()
    answer_sessions = set(question["answer_session_ids"])
    for sid, date, turns in zip(
        question["haystack_session_ids"], question["haystack_dates"],
        question["haystack_sessions"], strict=True,
    ):
        base = _ms(str(date))
        if granularity == "session":
            text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in turns)
            facts.append(SemanticFact(
                fact_id=len(facts) + 1, chat_key=str(question["question_id"]),
                subject=str(sid), fact_text=text[:max_chars] if max_chars else text,
                event_time_ms=base, confidence=1.0,
            ))
            if sid in answer_sessions:
                targets.add(facts[-1].fact_id)
            continue
        for index, turn in enumerate(turns):
            facts.append(SemanticFact(
                fact_id=len(facts) + 1, chat_key=str(question["question_id"]),
                subject=str(sid), fact_text=f"{turn['role']}: {turn['content']}",
                event_time_ms=base + index * 1000 if base else 0,
                confidence=1.0,
            ))
            if turn.get("has_answer"):
                targets.add(facts[-1].fact_id)
    return tuple(facts), targets


async def _ranked(
    question: dict[str, Any], facts: tuple[SemanticFact, ...],
    gateway: OpenAiEmbeddingGateway, retriever: str, batch: int, *,
    disabled: frozenset[str],
) -> tuple[SemanticFact, ...]:
    if retriever == "bm25":
        if not disabled:
            scores = bm25_scores(facts, str(question["question"]))
            return tuple(sorted(facts, key=lambda fact: (-scores[fact.fact_id], fact.fact_id)))
        return unified_rank(
            facts, str(question["question"]), {}, {},
            _ms(str(question["question_date"])), constraints=False, disabled=disabled,
        )
    vectors = await _embed_all(gateway, [fact.fact_text for fact in facts], batch)
    query_vec = (await gateway.embed((str(question["question"]),)))[0]
    dense = {fact.fact_id: cosine(query_vec, vec)
             for fact, vec in zip(facts, vectors, strict=True)}
    return unified_rank(
        facts, str(question["question"]), dense, {},
        _ms(str(question["question_date"])), constraints=False,
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--granularity", choices=("session", "turn"), default="session")
    parser.add_argument("--retriever", choices=("hybrid", "bm25"), default="hybrid")
    parser.add_argument("--disable", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "longmemeval.json")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    selected = _stratified(data, args.limit)
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    gateway = OpenAiEmbeddingGateway(cfg.embedding)
    results = []
    try:
        for question in selected:
            facts, target_ids = _facts(question, args.granularity)
            disabled = frozenset(x for x in args.disable.split(",") if x)
            ranked = await _ranked(
                question, facts, gateway, args.retriever, args.batch,
                disabled=disabled,
            )
            answer_sessions = set(question["answer_session_ids"])
            top5 = ranked[:5]
            turn_hit = (
                any(fact.fact_id in target_ids for fact in top5)
                if args.granularity == "turn" else None
            )
            session_hit = any(fact.subject in answer_sessions for fact in top5)
            first = next((index for index, fact in enumerate(ranked, 1)
                          if fact.fact_id in target_ids), None)
            results.append({
                "id": question["question_id"], "type": question["question_type"],
                "turn_hit": turn_hit, "session_hit": session_hit,
                "mrr": 1.0 / first if first else 0.0,
            })
            print(f"{question['question_id']} {question['question_type']} "
                  f"session={session_hit} mrr={results[-1]['mrr']:.3f}")
    finally:
        await gateway.aclose()

    summary = {}
    for kind in sorted({item["type"] for item in results}):
        rows = [item for item in results if item["type"] == kind]
        summary[kind] = {
            "n": len(rows),
            "turn_recall@5": (
                round(sum(item["turn_hit"] for item in rows) / len(rows), 3)
                if args.granularity == "turn" else None
            ),
            "session_recall@5": round(sum(item["session_hit"] for item in rows) / len(rows), 3),
            "mrr": round(sum(item["mrr"] for item in rows) / len(rows), 3),
        }
    report = {"benchmark": "LongMemEval-S", "granularity": args.granularity,
              "retriever": args.retriever, "disabled": args.disable, "n": len(results),
              "summary": summary, "results": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
