"""Explicit temporal/directional queries constrain the candidate set before RRF."""

from __future__ import annotations

from echomind.domain.models import SemanticFact
from echomind.mind.ranker_fusion import unified_rank

NOW = 1_000_000_000_000
DAY = 86_400_000


def _ids(ranked: tuple[SemanticFact, ...]) -> list[int]:
    return [f.fact_id for f in ranked]


def test_directional_query_drops_reversed_fact() -> None:
    forbidden = SemanticFact(
        fact_id=1, chat_key="g", subject="s", fact_text="A 把书还给 B"
    )
    target = SemanticFact(
        fact_id=2, chat_key="g", subject="s", fact_text="B 把书还给 A"
    )
    ranked = unified_rank((forbidden, target), "B 把书还给 A", {}, {}, NOW)
    assert _ids(ranked)[0] == 2


def test_newest_query_drops_older_fact() -> None:
    old = SemanticFact(
        fact_id=1, chat_key="g", subject="s", fact_text="去了上海",
        event_time_ms=NOW - 60 * DAY,
    )
    new = SemanticFact(
        fact_id=2, chat_key="g", subject="s", fact_text="去了上海",
        event_time_ms=NOW,
    )
    ranked = unified_rank((old, new), "最近去了哪里", {}, {}, NOW)
    assert _ids(ranked) == [2]


def test_generic_query_does_not_filter() -> None:
    old = SemanticFact(
        fact_id=1, chat_key="g", subject="s", fact_text="去了上海",
        event_time_ms=NOW - 60 * DAY,
    )
    new = SemanticFact(
        fact_id=2, chat_key="g", subject="s", fact_text="去了上海",
        event_time_ms=NOW,
    )
    ranked = unified_rank((old, new), "随便聊聊", {}, {}, NOW)
    assert len(ranked) == 2
