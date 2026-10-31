"""Trait memory ranker must never see facts rejected by the hard gate."""

from __future__ import annotations

from typing import Any

from echomind.domain.models import PersonaTrait, SemanticFact
from echomind.mind.facade_memory import gate_frame, select_facts
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


class _Reader:
    async def active_traits(self) -> tuple[PersonaTrait, ...]:
        return (PersonaTrait(trait_id=1, category="habit", trait_text="关心"),)


class _Links:
    async def link(self, link: object) -> None:
        raise AssertionError("not used")

    async def list_links(self, trait_id: int, limit: int = 50) -> tuple[Any, ...]:
        raise AssertionError("not used")

    async def ranker_scores(
        self, trait_ids: tuple[int, ...], memory_kind: str = "semantic"
    ) -> dict[int, float]:
        return {1: 1.0, 2: 1.0}  # both public and secret are linked


def _facts() -> tuple[SemanticFact, ...]:
    return (
        SemanticFact(fact_id=1, chat_key="g", subject="公开", fact_text="群规",
                     sensitivity="group", owner_id=""),
        SemanticFact(fact_id=2, chat_key="g", subject="秘密", fact_text="暗号",
                     sensitivity="secret", owner_id="L"),
    )


async def test_secret_is_gated_before_trait_ranking() -> None:
    gated, _ = await gate_frame(_facts(), (), frozenset(), "group:1", None)
    assert {fact.fact_id for fact in gated} == {1}
    service = SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)}), "m",
        trait_reader=_Reader(), trait_links=_Links(),
    )
    picked = await select_facts(service, gated, "群规", 5)
    assert [fact.fact_id for fact in picked] == [1]


async def test_private_requires_owner_before_ranking() -> None:
    facts = (
        SemanticFact(fact_id=1, chat_key="g", subject="公开", fact_text="群规",
                     sensitivity="group", owner_id=""),
        SemanticFact(fact_id=2, chat_key="g", subject="私事", fact_text="病情",
                     sensitivity="private", owner_id="L"),
    )
    absent, _ = await gate_frame(facts, (), frozenset(), "group:1", None)
    present, _ = await gate_frame(facts, (), frozenset({"L"}), "private:L", None)
    assert {fact.fact_id for fact in absent} == {1}
    assert {fact.fact_id for fact in present} == {1, 2}
