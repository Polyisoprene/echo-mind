"""Multi-hop relation boost for fact retrieval (P2)."""

from __future__ import annotations

from echomind.domain.memory_ports import IRelationStore
from echomind.domain.models import SemanticFact
from echomind.mind.entity_order import entities


class RelationResolver:
    def __init__(self, store: IRelationStore, max_hops: int = 2) -> None:
        self._store = store
        self._max_hops = max_hops

    async def _query_entities(self, query: str) -> set[str]:
        starts = set(entities(query))
        known = await self._store.entities()
        lower = query.lower()
        starts |= {name for name in known if name and name.lower() in lower}
        return starts

    async def boost_ids(
        self, facts: tuple[SemanticFact, ...], query: str
    ) -> set[int]:
        starts = await self._query_entities(query)
        if not starts:
            return set()
        reached = await self._store.reachable(tuple(starts), self._max_hops)
        boosted: set[int] = set()
        for fact in facts:
            fact_entities = set(entities(f"{fact.subject} {fact.fact_text}"))
            if fact.subject.lower() in reached or fact_entities & reached:
                boosted.add(fact.fact_id)
        return boosted


__all__ = ["RelationResolver"]
