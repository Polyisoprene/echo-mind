"""Cosine reranking over persisted memory vectors (D15)."""

from __future__ import annotations

import math

from echomind.domain.models import SemanticFact
from echomind.domain.ports import IEmbeddingGateway
from echomind.mind.ebbinghaus import fact_recency
from echomind.mind.entity_order import order_score

SEMANTIC_RECENCY_WEIGHT = 0.25
SEMANTIC_ORDER_WEIGHT = 0.5


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


async def rerank_facts(
    facts: tuple[SemanticFact, ...],
    query: str,
    embedder: IEmbeddingGateway,
    vectors: dict[int, tuple[float, ...]],
    limit: int = 28,
    *,
    now_ms: int = 0,
) -> tuple[SemanticFact, ...]:
    """Rank facts by query similarity; facts without vectors fall to the end."""
    if not facts:
        return ()
    query_vector = (await embedder.embed((query,)))[0]
    scored = [
        (cosine(query_vector, vectors.get(fact.fact_id, ()))
         + SEMANTIC_RECENCY_WEIGHT * fact_recency(fact.event_time_ms, now_ms)
         + SEMANTIC_ORDER_WEIGHT * order_score(
             query, f"{fact.subject} {fact.fact_text}"
         ), index, fact)
        for index, fact in enumerate(facts)
    ]
    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return tuple(fact for _, _, fact in scored[:limit])


__all__ = ["cosine", "rerank_facts"]
