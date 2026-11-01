#!/usr/bin/env python
"""GroupMemBench Finance adapter: message BM25 + official QA/judge prompts."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import load_config_from_json
from echomind.domain.models import SemanticFact
from echomind.mind.ranker_fusion import bm25_scores

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "external" / "GroupMemBench"


def _ts(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return 0


def _load(domain: str) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    path = (
        BENCH / "data" / "final" / domain
        / f"synthetic_domain_channels_rolevariants_{domain}.json"
    )
    channels = json.loads(path.read_text(encoding="utf-8"))
    messages: list[dict[str, Any]] = []
    for channel, entries in channels.items():
        for message in entries:
            item = dict(message)
            item["_channel"] = channel
            messages.append(item)
    messages.sort(key=lambda item: (str(item.get("timestamp", "")), str(item.get("msg_node", ""))))
    return messages, channels


def _fact(message: dict[str, Any], index: int) -> SemanticFact:
    return SemanticFact(
        fact_id=index, chat_key=str(message.get("_channel", "")),
        subject="", fact_text=str(message.get("content", "")),
        event_time_ms=_ts(str(message.get("timestamp", ""))),
    )


def _passage(message: dict[str, Any]) -> str:
    tags = [f"user={message.get('author') or '?'}"]
    for key, label in (("role", "speaker_role"), ("_channel", "channel"),
                       ("phase_name", "phase_name"), ("topic", "topic"),
                       ("timestamp", "timestamp"), ("reply_to", "reply_to"),
                       ("msg_node", "msg_node")):
        value = message.get(key)
        if value not in (None, ""):
            tags.append(f"{label}={value}")
    return f"[{' / '.join(tags)}]\n{str(message.get('content', '')).strip()}"


def _final(text: str) -> str:
    for line in reversed([line.strip() for line in text.splitlines() if line.strip()]):
        low = line.lower()
        if low.startswith("final:"):
            return line.split(":", 1)[1].strip()
        if low.startswith("final answer:"):
            return line.split(":", 1)[1].strip()
    return text.strip()


async def _reply(llm: FailoverLlmGateway, system: str, user: str, max_tokens: int) -> str:
    response = await llm.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0, max_tokens=max_tokens, thinking_off=True,
    )
    choices = response.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""
    return str(choices[0].get("message", {}).get("content") or "")


async def _ask(
    llm: FailoverLlmGateway, *,
    question: dict[str, Any], messages: list[dict[str, Any]],
    facts: tuple[SemanticFact, ...], agent: str, judge: str, topk: int,
) -> dict[str, Any]:
    query = f"{question.get('asking_user_id', '')} {question['question']}".strip()
    scores = bm25_scores(facts, query)
    top = sorted(
        facts, key=lambda fact: (-scores[fact.fact_id], fact.fact_id)
    )[:topk]
    passages = "\n\n".join(
        f"[{i}] {_passage(messages[fact.fact_id])}"
        for i, fact in enumerate(top, 1)
    )
    asker = f"Asking user: {question.get('asking_user_id', '')}\n\n"
    answer = await _reply(
        llm, agent,
        f"{asker}Question:\n{question['question']}\n\nRetrieved passages:\n{passages}\n\n"
        "Answer the question using the retrieved passages.", 512,
    )
    final = _final(answer)
    verdict = await _reply(
        llm, judge,
        f"Question:\n{question['question']}\n\nGold Answer:\n{question.get('answer', '')}\n\n"
        f"Agent Answer:\n{final}\n", 256,
    )
    jfinal = _final(verdict).lower()
    return {"answer": final, "correct": "correct" in jfinal and "incorrect" not in jfinal}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="Finance")
    parser.add_argument("--qtypes", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "groupmembench.json")
    parser.add_argument("--raw", type=Path, default=ROOT / "reports" / "groupmembench.jsonl")
    args = parser.parse_args()
    messages, _ = _load(args.domain)
    facts = tuple(_fact(message, index) for index, message in enumerate(messages))
    qdir = BENCH / "questions" / args.domain
    agent = (BENCH / "prompts" / "hipporag_agent_system.txt").read_text(encoding="utf-8")
    judge = (BENCH / "prompts" / "hipporag_judge_system.txt").read_text(encoding="utf-8")
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    db = SqliteDatabase(ROOT / "reports" / "groupmembench_trace.db")
    await db.initialize()
    llm = FailoverLlmGateway(cfg.primary_llm, cfg.fallback_llm, db,
                             extra_fallbacks=cfg.fallback_chain)
    rows: list[dict[str, Any]] = []
    summary: dict[str, Counter[str]] = {}
    args.raw.parent.mkdir(parents=True, exist_ok=True)
    with args.raw.open("w", encoding="utf-8") as raw:
        for qpath in sorted(qdir.glob("*.jsonl")):
            qtype = qpath.stem
            if args.qtypes and qtype not in args.qtypes.split(","):
                continue
            summary[qtype] = Counter()
            lines = [
                line for line in qpath.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if args.limit:
                lines = lines[:args.limit]
            for line in lines:
                q = json.loads(line)
                result = await _ask(
                    llm, question=q, messages=messages, facts=facts,
                    agent=agent, judge=judge, topk=args.topk,
                )
                rows.append({"qtype": qtype, "id": q.get("id"), "question": q["question"],
                             "answer": result["answer"], "gold": q.get("answer"),
                             "correct": result["correct"]})
                summary[qtype]["total"] += 1
                summary[qtype]["correct"] += int(result["correct"])
                raw.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
                raw.flush()
                print(f"{qtype}/{q.get('id')} correct={result['correct']}", flush=True)
    result = {kind: {"n": value["total"],
                     "accuracy": round(value["correct"] / max(1, value["total"]), 3)}
              for kind, value in summary.items()}
    total = sum(value["n"] for value in result.values())
    correct_total = sum(value["correct"] for value in summary.values())
    result["overall"] = {"n": total, "accuracy": round(correct_total / max(1, total), 3)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
