"""Role direction: relative entity order distinguishes A->B from B->A."""

from __future__ import annotations

from echomind.domain.models import SemanticFact
from echomind.mind.entity_order import order_score
from echomind.mind.ranker_fusion import unified_rank


def test_order_score_detects_reversal() -> None:
    assert order_score("B 把书还给 A", "B 把书还给了 A") == 1.0
    assert order_score("B 把书还给 A", "A 把书还给了 B") == -1.0
    assert order_score("今天天气", "今天天气不错") == 0.0


def test_selector_prefers_the_matching_direction() -> None:
    facts = (
        SemanticFact(fact_id=1, chat_key="g", subject="f1", fact_text="A 把书还给了 B"),
        SemanticFact(fact_id=2, chat_key="g", subject="f2", fact_text="B 把书还给了 A"),
    )
    picked = unified_rank(facts, "B 把书还给 A 了吗", {}, {}, 1_000)[:1]
    assert picked[0].subject == "f2"
