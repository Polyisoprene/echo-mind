"""The BDI stack is bounded and does not invent commitments."""

from __future__ import annotations

from echomind.domain.models import IntentionItem
from echomind.mind.intention_stack import expire_intentions, push_intention


def _item(summary: str, *, created: int = 1, expires: int = 100) -> IntentionItem:
    return IntentionItem(summary=summary, created_at_ms=created, expires_at_ms=expires)


def test_cap_is_three_and_keeps_latest() -> None:
    items: tuple[IntentionItem, ...] = ()
    for i in range(4):
        items = push_intention(items, _item(f"i{i}"))
    assert [i.summary for i in items] == ["i1", "i2", "i3"]


def test_duplicate_is_not_added_twice() -> None:
    item = _item("去群里说")
    assert push_intention((item,), item) == (item,)


def test_expired_intention_is_removed() -> None:
    assert expire_intentions((_item("a", expires=10),), 11) == ()
