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
    return _fill_normal(groups, limit, picked)


def _fill_normal(
    groups: dict[str, list[dict[str, Any]]], limit: int,
    picked: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for index in range(max(len(group) for group in groups.values())):
        for key in sorted(groups):
            if index < len(groups[key]) and len(picked) < limit:
                picked.append(groups[key][index])
    return picked


async def _retrieve(
    question: dict[str, Any], gateway: OpenAiEmbeddingGateway, topk: int, batch: int,
    max_chars: int,
) -> tuple[list[str], list[str]]:
    facts, _ = _facts(question, "session", max_chars)
    vectors = await _embed_all(gateway, [fact.fact_text for fact in facts], batch)
    query_vec = (await gateway.embed((str(question["question"]),)))[0]
    dense = {fact.fact_id: cosine(query_vec, vec)
             for fact, vec in zip(facts, vectors, strict=True)}
    ranked = unified_rank(
        facts, str(question["question"]), dense, {}, _ms(str(question["question_date"])),
        constraints=False,
    )
    top = list(ranked[:topk])
    return _dated(question, top), [str(fact.subject) for fact in top]


def _oracle_memories(
    question: dict[str, Any], max_chars: int,
) -> tuple[list[str], list[str]]:
    """Gold-session context: isolates reading from retrieval."""
    facts, _ = _facts(question, "session", max_chars)
    wanted = set(question["answer_session_ids"])
    chosen = [fact for fact in facts if fact.subject in wanted]
    return _dated(question, chosen), [str(fact.subject) for fact in chosen]


def _dated(question: dict[str, Any], facts: list[Any]) -> list[str]:
    dates = dict(zip(question["haystack_session_ids"], question["haystack_dates"], strict=True))
    ordered = sorted(facts, key=lambda fact: str(dates.get(fact.subject, "")))
    return [
        f"Session Date: {dates.get(fact.subject, '')}\n{fact.fact_text}"
        for fact in ordered
    ]


def _answer_prompt(
    question: str, question_date: str, memories: list[str], cot: bool,
) -> str:
    context = "\n\n".join(
        f"### Session {index + 1}:\n{text}" for index, text in enumerate(memories)
    )
    step = (
        "Answer the question step by step: first extract all the relevant "
        "information, and then reason over the information to get the answer."
        if cot else "Please answer the question based on the relevant chat history."
    )
    answer_tag = "Answer (step by step):" if cot else "Answer:"
    return (
        "I will give you several history chats between you and a user. "
        f"{step}\n\nHistory Chats:\n\n{context}\n\n"
        f"Current Date: {question_date}\nQuestion: {question}\n{answer_tag}"
    )


async def _answer(
    llm: FailoverLlmGateway, question: str, question_date: str, memories: list[str],
    cot: bool = False,
) -> str:
    prompt = _answer_prompt(question, question_date, memories, cot)
    response = await llm.complete(
        [{"role": "user", "content": prompt}],
        temperature=0.0, max_tokens=512 if not cot else 768, thinking_off=True,
    )
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
        "Model Response: {}\n\n"
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


async def _process_question(
    question: dict[str, Any], args: argparse.Namespace,
    embedding: OpenAiEmbeddingGateway, llm: FailoverLlmGateway,
) -> dict[str, Any]:
    abstention = "_abs" in str(question["question_id"])
    row: dict[str, Any] = {
        "id": question["question_id"], "type": question["question_type"],
        "abstention": abstention, "gold": question["answer"],
        "gold_sessions": list(question["answer_session_ids"]),
    }
    try:
        memories, memory_sessions = await _memories(question, args, embedding)
        answer = await _answer(
            llm, str(question["question"]), str(question["question_date"]), memories,
            args.cot,
        )
        row.update({"memory_sessions": memory_sessions, "answer": answer})
        if not args.skip_judge:
            row["correct"] = await _judge(llm, question, answer)
    except Exception as exc:  # noqa: BLE001 - keep the batch resumable
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


async def _memories(
    question: dict[str, Any], args: argparse.Namespace,
    embedding: OpenAiEmbeddingGateway,
) -> tuple[list[str], list[str]]:
    if args.oracle:
        return _oracle_memories(question, args.max_context_chars)
    return await _retrieve(
        question, embedding, args.topk, args.batch, args.max_context_chars
    )


def _summary(rows: list[dict[str, Any]], skip_judge: bool) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for kind in sorted({row["type"] for row in rows}):
        subset = [row for row in rows if row["type"] == kind]
        summary[kind] = {"n": len(subset), "accuracy": round(
            sum(1 for row in subset if row.get("correct")) / len(subset), 3
        ) if not skip_judge else None}
    if not skip_judge:
        abstention = [row for row in rows if row["abstention"]]
        summary["abstention"] = {
            "n": len(abstention),
            "accuracy": round(sum(1 for row in abstention if row.get("correct")) /
                              max(1, len(abstention)), 3),
        }
    return summary


def _write_report(
    out: Path, rows: list[dict[str, Any]], args: argparse.Namespace,
    summary: dict[str, Any],
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {"benchmark": "LongMemEval-S", "n": len(rows), "topk": args.topk,
              "oracle": args.oracle, "cot": args.cot,
              "max_context_chars": args.max_context_chars,
              "summary": summary, "rows": rows}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--oracle", action="store_true")
    parser.add_argument("--cot", action="store_true")
    parser.add_argument("--full-order", action="store_true")
    parser.add_argument("--max-context-chars", type=int, default=0)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "longmemeval_qa.json")
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    if args.full_order:
        all_selected = _select(data, len(data))
        selected = all_selected[args.offset:args.offset + args.limit]
    elif args.offset == 0 and args.limit < len(data):
        selected = _select(data, args.limit)
    else:
        all_selected = _select(data, len(data))
        selected = all_selected[args.offset:args.offset + args.limit]
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    embedding = OpenAiEmbeddingGateway(cfg.embedding)
    trace_db = SqliteDatabase(ROOT / "reports" / "longmemeval_qa_trace.db")
    await trace_db.initialize()
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, trace_db, extra_fallbacks=cfg.fallback_chain
    )
    rows: list[dict[str, Any]] = []
    if args.resume and args.out.is_file():
        rows = list(json.loads(args.out.read_text(encoding="utf-8")).get("rows", []))
    done = {str(row["id"]) for row in rows if not row.get("error")}
    try:
        for question in selected:
            if str(question["question_id"]) in done:
                continue
            abstention = "_abs" in str(question["question_id"])
            if args.oracle and abstention:
                continue
            row = await _process_question(question, args, embedding, llm)
            rows.append(row)
            _write_report(args.out, rows, args, _summary(rows, args.skip_judge))
            print(f"{row['id']} {row['type']} correct={row.get('correct')} "
                  f"error={bool(row.get('error'))}", flush=True)
    finally:
        await embedding.aclose()
    summary = _summary(rows, args.skip_judge)
    _write_report(args.out, rows, args, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
