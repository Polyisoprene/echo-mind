"""Hard negatives isolate each ranker's unique contribution."""

from __future__ import annotations

from dataclasses import dataclass

from echomind.domain.models import SemanticFact
from echomind.mind.ranker_fusion import unified_rank

NOW = 1_000_000_000_000
DAY = 86_400_000
ALL_RANKERS = frozenset({"bm25", "dense", "recency", "order", "relations", "confidence", "lock"})


@dataclass(frozen=True)
class Case:
    name: str
    forbidden: SemanticFact
    target: SemanticFact
    query: str
    dense: dict[int, float]
    relations: dict[int, float]
    disable: str


def _case(name: str, target: SemanticFact, forbidden: SemanticFact, query: str,
          *, dense: dict[int, float] | None = None,
          relations: dict[int, float] | None = None) -> Case:
    return Case(name, forbidden, target, query, dense or {}, relations or {}, name)


def _base(
    fid: int, *, event_time_ms: int = 0, confidence: float = 0.8,
    is_locked: bool = False,
) -> SemanticFact:
    return SemanticFact(
        fact_id=fid, chat_key="g", subject="s", fact_text="去了上海",
        event_time_ms=event_time_ms, confidence=confidence, is_locked=is_locked,
    )


def _cases() -> list[Case]:
    return [
        _case("recency",
              _base(2, event_time_ms=NOW), _base(1, event_time_ms=NOW - 60 * DAY), "最近怎么样"),
        _case("order",
              SemanticFact(fact_id=2, chat_key="g", subject="s", fact_text="B 把书还给 A"),
              SemanticFact(fact_id=1, chat_key="g", subject="s", fact_text="A 把书还给 B"),
              "B 把书还给 A"),
        _case("dense",
              SemanticFact(fact_id=2, chat_key="g", subject="s", fact_text="x"),
              SemanticFact(fact_id=1, chat_key="g", subject="s", fact_text="x"),
              "q", dense={2: 0.9, 1: 0.1}),
        _case("relations",
              SemanticFact(fact_id=2, chat_key="g", subject="b", fact_text="x"),
              SemanticFact(fact_id=1, chat_key="g", subject="c", fact_text="x"),
              "a", relations={2: 0.9}),
        _case("confidence",
              SemanticFact(fact_id=2, chat_key="g", subject="s", fact_text="x", confidence=0.95),
              SemanticFact(fact_id=1, chat_key="g", subject="s", fact_text="x", confidence=0.5),
              "q"),
        _case("lock",
              SemanticFact(fact_id=2, chat_key="g", subject="s", fact_text="x", is_locked=True),
              SemanticFact(fact_id=1, chat_key="g", subject="s", fact_text="x"),
              "q"),
        _case("bm25",
              SemanticFact(fact_id=2, chat_key="g", subject="s", fact_text="猫粮"),
              SemanticFact(fact_id=1, chat_key="g", subject="s", fact_text="电影"),
              "猫粮"),
    ]


def _target_wins(case: Case, disabled: frozenset[str]) -> bool:
    facts = (case.forbidden, case.target)
    ranked = unified_rank(
        facts, case.query, case.dense, case.relations, NOW, disabled=disabled
    )
    ids = [fact.fact_id for fact in ranked]
    return 2 in ids and (1 not in ids or ids.index(2) < ids.index(1))


def test_each_ranker_is_necessary_on_its_hard_case() -> None:
    for case in _cases():
        only = ALL_RANKERS - {case.disable}
        assert _target_wins(case, only), case.name
        assert not _target_wins(case, ALL_RANKERS), case.name


def test_constant_confidence_and_lock_do_not_dilute_bm25() -> None:
    facts = (
        SemanticFact(fact_id=1, chat_key="g", subject="a", fact_text="猫粮",
                     confidence=0.8, is_locked=False),
        SemanticFact(fact_id=2, chat_key="g", subject="b", fact_text="电影",
                     confidence=0.8, is_locked=False),
    )
    drop = frozenset({"dense", "recency", "order", "relations"})
    with_constant = unified_rank(facts, "猫粮", {}, {}, 1_000, disabled=drop)
    without_constant = unified_rank(
        facts, "猫粮", {}, {}, 1_000, disabled=drop | {"confidence", "lock"}
    )
    assert [fact.fact_id for fact in with_constant] == [
        fact.fact_id for fact in without_constant
    ]
