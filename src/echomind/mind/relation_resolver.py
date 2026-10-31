"""Multi-hop, validity-aware relation boost for fact retrieval (P2)."""

from __future__ import annotations

from echomind.domain.memory_ports import IRelationStore
from echomind.domain.models import SemanticFact
from echomind.domain.relation import RELATION_MAX_HOPS
from echomind.mind.entity_order import entities


class RelationResolver:
    def __init__(self, store: IRelationStore, max_hops: int = RELATION_MAX_HOPS) -> None:
        self._store = store
        self._max_hops = max_hops

    async def _query_entities(self, query: str) -> set[str]:
        starts = set(entities(query))
        known = await self._store.entities()
        lower = query.lower()
        starts |= {name for name in known if name and name.lower() in lower}
        return starts

    async def boost_ids(
        self, facts: tuple[SemanticFact, ...], query: str, now_ms: int
    ) -> dict[int, float]:
        starts = await self._query_entities(query)
        if not starts:
            return {}
        reached = await self._store.reachable_scored(
            tuple(starts), self._max_hops, now_ms
        )
        boosted: dict[int, float] = {}
        for fact in facts:
            fact_entities = set(entities(f"{fact.subject} {fact.fact_text}"))
            scores = [reached.get(fact.subject.lower(), 0.0)]
            scores.extend(reached.get(entity, 0.0) for entity in fact_entities)
            best = max(scores)
            if best > 0:
                boosted[fact.fact_id] = best
        return boosted


__all__ = ["RelationResolver"]
