"""P3: trait links are an optional, equal-weight RRF ranker."""

from __future__ import annotations

from echomind.domain.models import SemanticFact
from echomind.mind.ranker_fusion import unified_rank

ALL = frozenset({
    "bm25", "dense", "recency", "order", "relations", "confidence", "lock", "trait",
})


def _facts() -> tuple[SemanticFact, SemanticFact]:
    first = SemanticFact(fact_id=1, chat_key="g", subject="a", fact_text="旧记忆")
    second = SemanticFact(fact_id=2, chat_key="g", subject="b", fact_text="新记忆")
    return first, second


def test_trait_scores_can_rank_a_memory() -> None:
    ranked = unified_rank(
        _facts(), "记忆", {}, {}, 1_000,
        disabled=ALL - {"trait"}, trait_scores={2: 1.0},
    )
    assert [fact.fact_id for fact in ranked] == [2]


def test_empty_trait_scores_have_no_effect() -> None:
    ranked = unified_rank(
        _facts(), "记忆", {}, {}, 1_000, disabled=ALL - {"trait"},
    )
    assert ranked == ()
