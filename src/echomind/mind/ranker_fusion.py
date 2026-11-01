"""Weight-free multi-ranker fusion using RRF (lexical/BM25, dense, time, order, relations)."""

from __future__ import annotations

import math
from collections import Counter

from echomind.domain.models import SemanticFact
from echomind.mind.ebbinghaus import TOKEN_RE
from echomind.mind.entity_order import order_score
from echomind.mind.retrieval_fusion import RRF_K, rrf_fuse

_NEW_TIME = ("最近", "现在", "刚刚", "最新", "当前")
_OLD_TIME = ("之前", "以前", "上次", "原来")
_DIRECTION = ("把", "给", "还给", "送给", "借给", "告诉", "问")
_TEMPORAL_QUESTION = ("哪", "什么时候", "多久", "几月", "哪天", "之前", "之后")

BM25_K1 = 1.2
BM25_B = 0.75


def _terms(text: str) -> list[str]:
    terms: list[str] = []
    for chunk in TOKEN_RE.findall(text):
        if chunk.isascii() or len(chunk) <= 2:
            terms.append(chunk)
        else:
            terms.extend(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return terms


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
    tokens = [_terms(f"{fact.subject} {fact.fact_text}") for fact in facts]
    query_terms = set(_terms(query))
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


def _temporal_mode(query: str) -> bool | None:
    if not any(cue in query for cue in _TEMPORAL_QUESTION):
        return None
    if any(cue in query for cue in _NEW_TIME):
        return True
    if any(cue in query for cue in _OLD_TIME):
        return False
    return None


def _temporal_filter(
    facts: tuple[SemanticFact, ...], query: str
) -> tuple[SemanticFact, ...] | None:
    newest = _temporal_mode(query)
    if newest is None:
        return None
    times = [f.event_time_ms for f in facts if f.event_time_ms > 0]
    if not times:
        return None
    edge = max(times) if newest else min(times)
    return tuple(f for f in facts if f.event_time_ms == edge)

def _direction_filter(
    facts: tuple[SemanticFact, ...], query: str
) -> tuple[SemanticFact, ...] | None:
    if not any(cue in query for cue in _DIRECTION):
        return None
    order = {f.fact_id: order_score(query, f"{f.subject} {f.fact_text}") for f in facts}
    if min(order.values()) < 0 < max(order.values()):
        return tuple(f for f in facts if order[f.fact_id] >= 0)
    return None


def _apply_constraints(
    facts: tuple[SemanticFact, ...], query: str
) -> tuple[SemanticFact, ...]:
    return _temporal_filter(facts, query) or _direction_filter(facts, query) or facts

def _candidate_rankers(
    facts: tuple[SemanticFact, ...], query: str,
    dense: dict[int, float], relations: dict[int, float], now_ms: int,
    *, trait_scores: dict[int, float] | None = None,
) -> dict[str, tuple[int, ...]]:
    recency = {f.fact_id: float(f.event_time_ms) for f in facts}
    order = {f.fact_id: order_score(query, f"{f.subject} {f.fact_text}") for f in facts}
    confidence = {f.fact_id: f.confidence for f in facts}
    lock = {f.fact_id: 1.0 if f.is_locked else 0.0 for f in facts}
    lexical = bm25_scores(facts, query)
    # Trait support may amplify a lexically grounded memory, never create one.
    grounded_trait = {
        fact_id: score for fact_id, score in (trait_scores or {}).items()
        if lexical.get(fact_id, 0.0) > 0.0
    }
    return {
        "bm25": _rank(lexical),
        "dense": _rank(dense),
        "recency": _rank(recency),
        "order": _rank(order),
        "relations": _rank(relations),
        "confidence": _rank(confidence),
        "lock": _rank(lock),
        "trait": _rank(grounded_trait),
    }


def unified_rank(
    facts: tuple[SemanticFact, ...], query: str,
    dense: dict[int, float], relations: dict[int, float], now_ms: int,
    *, disabled: frozenset[str] = frozenset(), constraints: bool = True,
    trait_scores: dict[int, float] | None = None,
) -> tuple[SemanticFact, ...]:
    """Fuse independent signals as ranks; no hand-tuned feature weights."""
    if not facts:
        return ()
    if constraints:
        facts = _apply_constraints(facts, query)
    if not facts:
        return ()
    candidates = _candidate_rankers(
        facts, query, dense, relations, now_ms, trait_scores=trait_scores
    )
    rankers = tuple(
        items for name, items in candidates.items() if name not in disabled
    )
    fused = rrf_fuse(rankers, RRF_K)
    by_id = {fact.fact_id: fact for fact in facts}
    return tuple(by_id[fact_id] for fact_id in fused if fact_id in by_id)

__all__ = ["BM25_B", "BM25_K1", "bm25_scores", "unified_rank"]
