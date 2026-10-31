"""Optional semantic reranking service for memory retrieval (D15)."""

from __future__ import annotations

import logging

from echomind.domain.models import SemanticFact
from echomind.domain.ports import IEmbeddingGateway, IMemoryVectorStore
from echomind.mind.relation_resolver import RelationResolver
from echomind.mind.semantic_retrieval import rerank_facts

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
        self, facts: tuple[SemanticFact, ...], query: str
    ) -> set[int]:
        if self._relations is None:
            return set()
        return await self._relations.boost_ids(facts, query)

    async def rerank(
        self, facts: tuple[SemanticFact, ...], query: str, limit: int,
        now_ms: int = 0,
    ) -> tuple[SemanticFact, ...] | None:
        ids = tuple(f.fact_id for f in facts if f.fact_id)
        vectors = await self._store.get("semantic", ids, self._model)
        if len(vectors) < max(1, len(facts) // 2):
            return None
        try:
            return await rerank_facts(
                facts, query, self._embedder, vectors, limit, now_ms=now_ms
            )
        except Exception:  # noqa: BLE001 - fall back to lexical retrieval
            logger.warning("semantic rerank failed; falling back", exc_info=True)
            return None


__all__ = ["SemanticMemoryRetriever"]
