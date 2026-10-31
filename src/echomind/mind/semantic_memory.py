"""Optional semantic reranking service for memory retrieval (D15)."""

from __future__ import annotations

import logging

from echomind.domain.models import SemanticFact
from echomind.domain.ports import IEmbeddingGateway, IMemoryVectorStore
from echomind.mind.ranker_fusion import unified_rank
from echomind.mind.relation_resolver import RelationResolver
from echomind.mind.semantic_retrieval import cosine, rerank_facts

logger = logging.getLogger(__name__)


class SemanticMemoryRetriever:
    """Rerank facts with stored vectors; returns None when coverage is too low."""

    def __init__(
        self, embedder: IEmbeddingGateway, store: IMemoryVectorStore, model: str,
        relations: RelationResolver | None = None,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._model = model
        self._relations = relations

    async def boost_ids(
        self, facts: tuple[SemanticFact, ...], query: str, now_ms: int
    ) -> dict[int, float]:
        if self._relations is None:
            return {}
        return await self._relations.boost_ids(facts, query, now_ms)

    async def rank_fused(
        self, facts: tuple[SemanticFact, ...], query: str, now_ms: int
    ) -> tuple[SemanticFact, ...] | None:
        if not facts:
            return ()
        ids = tuple(f.fact_id for f in facts if f.fact_id)
        vectors = await self._store.get("semantic", ids, self._model)
        if len(vectors) < max(1, len(facts) // 2):
            return None
        try:
            query_vector = (await self._embedder.embed((query,)))[0]
            dense = {
                f.fact_id: cosine(query_vector, vectors[f.fact_id])
                for f in facts if f.fact_id in vectors
            }
            relations = await self.boost_ids(facts, query, now_ms)
            return unified_rank(facts, query, dense, relations, now_ms)
        except Exception:  # noqa: BLE001 - fall back to lexical retrieval
            logger.warning("fused ranking failed; falling back", exc_info=True)
            return None

    async def rerank(
        self, facts: tuple[SemanticFact, ...], query: str, limit: int
    ) -> tuple[SemanticFact, ...] | None:
        ids = tuple(f.fact_id for f in facts if f.fact_id)
        vectors = await self._store.get("semantic", ids, self._model)
        if len(vectors) < max(1, len(facts) // 2):
            return None
        try:
            return await rerank_facts(facts, query, self._embedder, vectors, limit)
        except Exception:  # noqa: BLE001 - fall back to lexical retrieval
            logger.warning("semantic rerank failed; falling back", exc_info=True)
            return None


__all__ = ["SemanticMemoryRetriever"]
