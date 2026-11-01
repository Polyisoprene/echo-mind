"""Supersede planner is functional-value only and privacy-conservative."""

from __future__ import annotations

from echomind.mind.claim_supersede import plan_supersedes
from echomind.mind.fact_shadow import ClaimView


def _view(value: str, *, recorded: int, predicate: str = "value",
          audience: tuple[str, ...] = ("L",)) -> ClaimView:
    return ClaimView(
        subject="群主", value=value, predicate=predicate, belief=0.8,
        recorded_at_ms=recorded, locked=False, chat_key="g",
        scope="venue", owner_id="", sensitivity="group", audience=audience,
    )


def test_older_value_with_same_audience_is_superseded() -> None:
    old = _view("A", recorded=1)
    new = _view("B", recorded=2)
    assert plan_supersedes(new, (old,)) == (old,)


def test_mentioned_is_never_superseded() -> None:
    old = _view("A", recorded=1, predicate="mentioned")
    new = _view("B", recorded=2)
    assert plan_supersedes(new, (old,)) == ()


def test_different_audience_is_not_superseded() -> None:
    old = _view("A", recorded=1, audience=("L",))
    new = _view("B", recorded=2, audience=("M",))
    assert plan_supersedes(new, (old,)) == ()
