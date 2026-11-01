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
from echomind.adapters.llm.embedding_client import OpenAiEmbeddingGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import load_config_from_json
from echomind.domain.models import SemanticFact
from echomind.mind.ranker_fusion import bm25_scores
from echomind.mind.retrieval_fusion import RRF_K, rrf_fuse
from echomind.mind.semantic_retrieval import cosine

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


def _fact(message: dict[str, Any], index: int, *, metadata: bool = False) -> SemanticFact:
    text = str(message.get("content", ""))
    if metadata:
        text = " ".join([
            text,
            str(message.get("author", "")), str(message.get("role", "")),
            str(message.get("_channel", "")), str(message.get("phase_name", "")),
            str(message.get("topic", "")),
        ])
    return SemanticFact(
        fact_id=index, chat_key=str(message.get("_channel", "")),
        subject="", fact_text=text,
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


async def _load_vectors(
    embedding: OpenAiEmbeddingGateway, facts: tuple[SemanticFact, ...], batch: int,
) -> list[tuple[float, ...]]:
    vectors: list[tuple[float, ...]] = []
    for start in range(0, len(facts), batch):
        vectors.extend(await embedding.embed(
            tuple(fact.fact_text for fact in facts[start:start + batch])
        ))
    return vectors


async def _ask(
    llm: FailoverLlmGateway, *,
    question: dict[str, Any], messages: list[dict[str, Any]],
    facts: tuple[SemanticFact, ...], agent: str, judge: str, topk: int,
    retriever: str = "bm25", vectors: list[tuple[float, ...]] | None = None,
    embedding: OpenAiEmbeddingGateway | None = None, sort_context: bool = False,
    no_asker: bool = False,
) -> dict[str, Any]:
    asker_id = "" if no_asker else str(question.get("asking_user_id", ""))
    query = f"{asker_id} {question['question']}".strip()
    if retriever == "bm25":
        scores = bm25_scores(facts, query)
        top = sorted(
            facts, key=lambda fact: (-scores[fact.fact_id], fact.fact_id)
        )[:topk]
    else:
        if vectors is None or embedding is None:
            raise ValueError("dense retrieval requires vectors and embedding")
        query_vec = (await embedding.embed((query,)))[0]
        dense = {fact.fact_id: cosine(query_vec, vectors[fact.fact_id])
                 for fact in facts}
        if retriever == "dense":
            top = sorted(
                facts, key=lambda fact: (-dense[fact.fact_id], fact.fact_id)
            )[:topk]
        else:
            lexical = bm25_scores(facts, query)
            lex_rank = tuple(sorted(lexical, key=lambda i: (-lexical[i], i)))
            dense_rank = tuple(sorted(dense, key=lambda i: (-dense[i], i)))
            fused = rrf_fuse((lex_rank, dense_rank), RRF_K)
            by_id = {fact.fact_id: fact for fact in facts}
            top = [by_id[i] for i in fused[:topk]]
    docs = [_passage(messages[fact.fact_id]) for fact in top]
    passages = "\n\n".join(
        f"[{i}] {doc}" for i, doc in enumerate(docs, 1)
    )
    asker = f"Asking user: {asker_id}\n\n" if asker_id else ""
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
    return {
        "answer": final, "retrieved_docs": docs,
        "correct": "correct" in jfinal and "incorrect" not in jfinal,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="Finance")
    parser.add_argument("--qtypes", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--retriever", choices=("bm25", "dense", "hybrid"), default="bm25")
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--index-metadata", action="store_true")
    parser.add_argument("--sort-context", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--no-asker", action="store_true")
    parser.add_argument("--decision-only", action="store_true")
    parser.add_argument("--change-only", action="store_true")
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "groupmembench.json")
    parser.add_argument("--raw", type=Path, default=ROOT / "reports" / "groupmembench.jsonl")
    return parser.parse_args()


def _search_facts(
    args: argparse.Namespace, facts: tuple[SemanticFact, ...],
    decision_facts: tuple[SemanticFact, ...], changed_facts: tuple[SemanticFact, ...],
) -> tuple[SemanticFact, ...]:
    if args.change_only:
        return changed_facts
    if args.decision_only:
        return decision_facts
    return facts


async def main() -> int:
    args = _parse_args()
    messages, _ = _load(args.domain)
    facts = tuple(
        _fact(message, index, metadata=args.index_metadata)
        for index, message in enumerate(messages)
    )
    decision_facts = tuple(
        fact for fact, message in zip(facts, messages, strict=True)
        if message.get("is_decision_point")
    )
    changed_facts = tuple(
        fact for fact, message in zip(facts, messages, strict=True)
        if message.get("decision_type") == "changed"
        or message.get("decision_change_metadata")
    )
    qdir = BENCH / "questions" / args.domain
    agent = (BENCH / "prompts" / "hipporag_agent_system.txt").read_text(encoding="utf-8")
    judge = (BENCH / "prompts" / "hipporag_judge_system.txt").read_text(encoding="utf-8")
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    embedding = (
        OpenAiEmbeddingGateway(cfg.embedding)
        if args.retriever in ("dense", "hybrid") else None
    )
    vectors = await _load_vectors(embedding, facts, args.batch) if embedding else None
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
                search_facts = _search_facts(args, facts, decision_facts, changed_facts)
                result = await _ask(
                    llm, question=q, messages=messages, facts=search_facts,
                    agent=agent, judge=judge, topk=args.topk,
                    retriever=args.retriever, vectors=vectors, embedding=embedding,
                    sort_context=args.sort_context, no_asker=args.no_asker,
                )
                row = {"qtype": qtype, "id": q.get("id"), "question": q["question"],
                       "answer": result["answer"], "gold": q.get("answer"),
                       "correct": result["correct"]}
                if args.diagnose:
                    row["retrieved_docs"] = result["retrieved_docs"]
                rows.append(row)
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
