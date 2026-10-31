"""High-precision relation extraction patterns."""

from __future__ import annotations

from echomind.mind.relation_extractor import extract


def test_extracts_work_friend_gift_and_alias() -> None:
    assert extract("B", "B 在 X 工作")[0].predicate == "works_at"
    assert extract("A", "A 是 B 的朋友")[0].predicate == "friend"
    assert extract("A", "A 把书给了 B")[0].predicate == "gave_to"
    alias = extract("x", "QQ:3993173948 的群友是「汐」")[0]
    assert (alias.predicate, alias.subject, alias.object) == ("alias", "3993173948", "汐")


def test_ignores_unstructured_text() -> None:
    assert extract("A", "今天天气不错") == ()
