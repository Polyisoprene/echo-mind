"""D15: the semantic retriever reranks when vectors cover enough facts."""

from __future__ import annotations

import pytest

from echomind.domain.models import SemanticFact
from echomind.mind.facade_memory import select_facts
from echomind.mind.semantic_memory import SemanticMemoryRetriever


class _Store:
    def __init__(self, vectors: dict[int, tuple[float, ...]]) -> None:
        self._vectors = vectors

    async def get(
        self, memory_kind: str, memory_ids: tuple[int, ...]
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
        _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)})
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
        _Embedder(), _Store({1: (1.0, 0.0)})
    )
    assert await service.rerank(facts, "宠物", 1) is None


@pytest.mark.asyncio
async def test_frame_falls_back_to_lexical_without_semantic() -> None:
    picked = await select_facts(None, _facts(), "猫", 1)
    assert len(picked) == 1
