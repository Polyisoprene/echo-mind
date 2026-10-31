"""D15: cosine reranking puts the semantically closest fact first."""

from __future__ import annotations

import pytest

from echomind.domain.models import SemanticFact
from echomind.mind.semantic_retrieval import cosine, rerank_facts


class _Embedder:
    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return ((1.0, 0.0),)


def _fact(fact_id: int, text: str) -> SemanticFact:
    return SemanticFact(fact_id=fact_id, chat_key="g", subject=f"s{fact_id}", fact_text=text)


def test_cosine_basics() -> None:
    assert cosine((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert cosine((1.0, 0.0), (1.0,)) == 0.0


@pytest.mark.asyncio
async def test_rerank_prefers_the_matching_vector() -> None:
    facts = (_fact(1, "猫粮"), _fact(2, "电影"))
    ranked = await rerank_facts(
        facts, "宠物", _Embedder(), {1: (1.0, 0.0), 2: (0.0, 1.0)}, limit=1
    )
    assert ranked[0].fact_text == "猫粮"
