#!/usr/bin/env python
"""LongMemEval QA/abstention using the official judge prompts."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from eval_longmemeval import _embed_all, _facts, _ms  # type: ignore[import-not-found]

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.llm.embedding_client import OpenAiEmbeddingGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import load_config_from_json
from echomind.mind.ranker_fusion import unified_rank
from echomind.mind.semantic_retrieval import cosine

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "external" / "longmemeval_s.json"


def _select(data: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit >= len(data):
        return data
    picked: list[dict[str, Any]] = []
    for item in data:
        if "_abs" in str(item["question_id"]) and len(picked) < min(5, limit):
            picked.append(item)
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in data:
        if "_abs" not in str(item["question_id"]):
            groups.setdefault(str(item["question_type"]), []).append(item)
    for index in range(max(len(group) for group in groups.values())):
        for key in sorted(groups):
            if index < len(groups[key]) and len(picked) < limit:
                picked.append(groups[key][index])
    return picked


async def _retrieve(
    question: dict[str, Any], gateway: OpenAiEmbeddingGateway, topk: int, batch: int,
) -> list[str]:
    facts, _ = _facts(question, "session")
    vectors = await _embed_all(gateway, [fact.fact_text for fact in facts], batch)
    query_vec = (await gateway.embed((str(question["question"]),)))[0]
    dense = {fact.fact_id: cosine(query_vec, vec)
             for fact, vec in zip(facts, vectors, strict=True)}
    ranked = unified_rank(
        facts, str(question["question"]), dense, {}, _ms(str(question["question_date"])),
        constraints=False,
    )
    return [fact.fact_text for fact in ranked[:topk]]


async def _answer(llm: FailoverLlmGateway, question: str, memories: list[str]) -> str:
    context = "\n\n".join(f"[{index + 1}] {text}" for index, text in enumerate(memories))
    response = await llm.complete([
        {"role": "system", "content": "只使用给出的 memories 回答；证据不足就说 I don't know。"},
        {"role": "user", "content": f"Memories:\n{context}\n\nQuestion: {question}\nAnswer:"},
    ], temperature=0.0, max_tokens=512, thinking_off=True)
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    return str(message.get("content") or "").strip()


def _judge_prompt(question: dict[str, Any], response: str) -> str:
    task = str(question["question_type"])
    abstention = "_abs" in str(question["question_id"])
    if abstention:
        return (
            "I will give you an unanswerable question, an explanation, and a response "
            "from a model. Please answer yes if the model correctly identifies the question "
            "as unanswerable. The model could say that the information is incomplete, or "
            "some other information is given but the asked information is not.\n\n"
            "Question: {}\n\nExplanation: {}\n\nModel Response: {}\n\n"
            "Does the model correctly identify the question as unanswerable? "
            "Answer yes or no only."
        ).format(question["question"], question["answer"], response)
    if task == "single-session-preference":
        return (
            "I will give you a question, a rubric for desired personalized response, "
            "and a response from a model. Please answer yes if the response satisfies the "
            "desired response. Otherwise, answer no. The model does not need to reflect "
            "all the points in the rubric. The response is correct as long as it recalls "
            "and utilizes the user's personal information correctly.\n\nQuestion: {}\n\n"
            "Rubric: {}\n\nModel Response: {}\n\n"
            "Is the model response correct? Answer yes or no only."
        ).format(question["question"], question["answer"], response)
    extra = ""
    if task == "temporal-reasoning":
        extra = "Do not penalize off-by-one errors for the number of days. "
    if task == "knowledge-update":
        extra = (
            "If previous information is included with the updated answer, "
            "prefer the updated answer. "
        )
    return (
        "I will give you a question, a correct answer, and a response from a model. "
        "Please answer yes if the response contains the correct answer. Otherwise, answer no. "
        "If the response is equivalent to the correct answer or contains all the intermediate "
        "steps to get the correct answer, you should also answer yes. "
        f"{extra}\n\nQuestion: {{}}\n\nCorrect Answer: {{}}\n\n"
        "Model Response: {{}}\n\n"
        "Is the model response correct? Answer yes or no only."
    ).format(question["question"], question["answer"], response)


async def _judge(llm: FailoverLlmGateway, question: dict[str, Any], response: str) -> bool:
    result = await llm.complete(
        [{"role": "user", "content": _judge_prompt(question, response)}],
        temperature=0.0, max_tokens=64, thinking_off=True,
    )
    choices = result.get("choices", [])
    text = ""
    if choices and isinstance(choices[0], dict):
        text = str(choices[0].get("message", {}).get("content") or "")
    return "yes" in text.lower()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "longmemeval_qa.json")
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    selected = _select(data, args.limit)
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    embedding = OpenAiEmbeddingGateway(cfg.embedding)
    trace_db = SqliteDatabase(ROOT / "reports" / "longmemeval_qa_trace.db")
    await trace_db.initialize()
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, trace_db, extra_fallbacks=cfg.fallback_chain
    )
    rows: list[dict[str, Any]] = []
    try:
        for question in selected:
            memories = await _retrieve(question, embedding, args.topk, args.batch)
            answer = await _answer(llm, str(question["question"]), memories)
            row = {"id": question["question_id"], "type": question["question_type"],
                   "abstention": "_abs" in str(question["question_id"]),
                   "answer": answer, "gold": question["answer"]}
            if not args.skip_judge:
                row["correct"] = await _judge(llm, question, answer)
            rows.append(row)
            print(f"{row['id']} {row['type']} correct={row.get('correct')}")
    finally:
        await embedding.aclose()
    summary: dict[str, Any] = {}
    for kind in sorted({row["type"] for row in rows}):
        subset = [row for row in rows if row["type"] == kind]
        summary[kind] = {"n": len(subset), "accuracy": round(
            sum(1 for row in subset if row.get("correct")) / len(subset), 3
        ) if not args.skip_judge else None}
    if not args.skip_judge:
        summary["abstention"] = {
            "n": sum(1 for row in rows if row["abstention"]),
            "accuracy": round(sum(1 for row in rows
                if row["abstention"] and row.get("correct")) /
                max(1, sum(1 for row in rows if row["abstention"])), 3),
        }
    report = {"benchmark": "LongMemEval-S", "n": len(rows), "topk": args.topk,
              "summary": summary, "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
