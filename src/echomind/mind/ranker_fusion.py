"""Weight-free multi-ranker fusion using RRF (lexical/BM25, dense, time, order, relations)."""

from __future__ import annotations

import math
from collections import Counter

from echomind.domain.models import SemanticFact
from echomind.mind.ebbinghaus import TOKEN_RE, fact_recency
from echomind.mind.entity_order import order_score
from echomind.mind.retrieval_fusion import RRF_K, rrf_fuse

BM25_K1 = 1.2
BM25_B = 0.75


def _bm25_one(
    counts: Counter[str], doc_len: int, *,
    query_terms: set[str], df: Counter[str], n: int, avgdl: float,
) -> float:
    score = 0.0
    for term in query_terms:
        tf = counts.get(term, 0)
        if not tf:
            continue
        idf = math.log(1.0 + (n - df[term] + 0.5) / (df[term] + 0.5))
        denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * doc_len / max(1.0, avgdl))
        score += idf * tf * (BM25_K1 + 1) / max(1e-9, denom)
    return score


def bm25_scores(facts: tuple[SemanticFact, ...], query: str) -> dict[int, float]:
    tokens = [TOKEN_RE.findall(f"{fact.subject} {fact.fact_text}") for fact in facts]
    query_terms = set(TOKEN_RE.findall(query))
    n = len(facts)
    avgdl = sum(len(doc) for doc in tokens) / max(1, n)
    df: Counter[str] = Counter()
    for doc in tokens:
        df.update(set(doc))
    scores: dict[int, float] = {}
    for fact, doc in zip(facts, tokens, strict=True):
        scores[fact.fact_id] = _bm25_one(
            Counter(doc), len(doc),
            query_terms=query_terms, df=df, n=n, avgdl=avgdl,
        )
    return scores


def _rank(scores: dict[int, float]) -> tuple[int, ...]:
    return tuple(sorted(scores, key=lambda item: (-scores[item], item)))


def _candidate_rankers(
    facts: tuple[SemanticFact, ...], query: str,
    dense: dict[int, float], relations: dict[int, float], now_ms: int,
) -> dict[str, tuple[int, ...]]:
    recency = {f.fact_id: fact_recency(f.event_time_ms, now_ms) for f in facts}
    order = {f.fact_id: order_score(query, f"{f.subject} {f.fact_text}") for f in facts}
    confidence = {f.fact_id: f.confidence for f in facts}
    lock = {f.fact_id: 1.0 if f.is_locked else 0.0 for f in facts}
    return {
        "bm25": _rank(bm25_scores(facts, query)),
        "dense": _rank(dense),
        "recency": _rank(recency),
        "order": _rank(order),
        "relations": _rank(relations),
        "confidence": _rank(confidence),
        "lock": _rank(lock),
    }


def unified_rank(
    facts: tuple[SemanticFact, ...], query: str,
    dense: dict[int, float], relations: dict[int, float], now_ms: int,
    *, disabled: frozenset[str] = frozenset(),
) -> tuple[SemanticFact, ...]:
    """Fuse independent signals as ranks; no hand-tuned feature weights."""
    candidates = _candidate_rankers(facts, query, dense, relations, now_ms)
    rankers = tuple(
        items for name, items in candidates.items() if name not in disabled
    )
    fused = rrf_fuse(rankers, RRF_K)
    by_id = {fact.fact_id: fact for fact in facts}
    return tuple(by_id[fact_id] for fact_id in fused if fact_id in by_id)

__all__ = ["BM25_B", "BM25_K1", "bm25_scores", "unified_rank"]
