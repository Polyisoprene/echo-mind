"""D15: the semantic retriever reranks when vectors cover enough facts."""

from __future__ import annotations

from typing import Any

import pytest

from echomind.domain.models import SemanticFact
from echomind.mind.facade_memory import select_facts
from echomind.mind.semantic_memory import SemanticMemoryRetriever


class _Store:
    def __init__(self, vectors: dict[int, tuple[float, ...]]) -> None:
        self._vectors = vectors

    async def get(
        self, memory_kind: str, memory_ids: tuple[int, ...], model: str = ""
    ) -> dict[int, tuple[float, ...]]:
        return {k: v for k, v in self._vectors.items() if k in memory_ids}


class _Embedder:
    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return ((1.0, 0.0),)


def _facts() -> tuple[SemanticFact, ...]:
    return (
        SemanticFact(fact_id=1, chat_key="g", subject="猫", fact_text="猫粮"),
        SemanticFact(fact_id=2, chat_key="g", subject="电影", fact_text="催泪"),
    )


@pytest.mark.asyncio
async def test_rerank_with_full_coverage() -> None:
    service = SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)}), "m"
    )
    ranked = await service.rerank(_facts(), "宠物", 1)
    assert ranked is not None and ranked[0].fact_text == "猫粮"


@pytest.mark.asyncio
async def test_low_coverage_falls_back() -> None:
    facts = _facts() + (
        SemanticFact(fact_id=3, chat_key="g", subject="工作", fact_text="岗位"),
        SemanticFact(fact_id=4, chat_key="g", subject="睡眠", fact_text="熬夜"),
    )
    service = SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0)}), "m"
    )
    assert await service.rerank(facts, "宠物", 1) is None


@pytest.mark.asyncio
async def test_frame_falls_back_to_lexical_without_semantic() -> None:
    picked = await select_facts(None, _facts(), "猫", 1)
    assert len(picked) == 1


@pytest.mark.asyncio
async def test_fused_ranking_and_live_selector() -> None:
    service = SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)}), "m"
    )
    fused = await service.rank_fused(_facts(), "宠物", 1_000)
    assert fused is not None and fused[0].fact_text == "猫粮"
    picked = await select_facts(service, _facts(), "宠物", 1)
    assert picked[0].fact_text == "猫粮"


@pytest.mark.asyncio
async def test_low_coverage_uses_lexical_ranker_fusion() -> None:
    facts = _facts() + (
        SemanticFact(fact_id=3, chat_key="g", subject="工作", fact_text="岗位"),
        SemanticFact(fact_id=4, chat_key="g", subject="睡眠", fact_text="熬夜"),
    )
    service = SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0)}), "m"
    )
    picked = await select_facts(service, facts, "猫", 1)
    assert picked[0].fact_text == "猫粮"


class _TraitReader:
    async def active_traits(self) -> tuple[Any, ...]:
        from echomind.domain.models import PersonaTrait
        return (PersonaTrait(trait_id=7, category="habit", trait_text="t"),)


class _TraitLinks:
    def __init__(self) -> None:
        self.seen: tuple[int, ...] = ()

    async def link(self, link: object) -> None:
        raise AssertionError("not used")

    async def list_links(self, trait_id: int, limit: int = 50) -> tuple[Any, ...]:
        raise AssertionError("not used")

    async def ranker_scores(
        self, trait_ids: tuple[int, ...], memory_kind: str = "semantic"
    ) -> dict[int, float]:
        self.seen = trait_ids
        return {2: 1.0}


@pytest.mark.asyncio
async def test_active_trait_scores_are_injected_into_fusion() -> None:
    links = _TraitLinks()
    service = SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)}), "m",
        trait_reader=_TraitReader(), trait_links=links,
    )
    assert await service.active_trait_scores() == {2: 1.0}
    assert links.seen == (7,)


@pytest.mark.asyncio
async def test_no_trait_links_means_empty_scores() -> None:
    service = SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)}), "m"
    )
    assert await service.active_trait_scores() == {}
