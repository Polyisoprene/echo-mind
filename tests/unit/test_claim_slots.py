"""Slot inference is conservative and only marks person traits."""

from __future__ import annotations

from echomind.mind.claim_slots import infer_slot, is_single


def test_nickname_is_single() -> None:
    slot = infer_slot("L", "L的群昵称是「小L」")
    assert slot == "person.nickname"
    assert is_single(slot)


def test_preference_is_not_a_slot() -> None:
    assert infer_slot("L", "L喜欢吃草莓蛋糕") == ""


def test_mentioned_and_experience_are_not_slots() -> None:
    assert infer_slot("L", "L提到今天在忙") == ""
    assert infer_slot("L", "L在玩格斗游戏") == ""


def test_ambiguous_match_returns_empty() -> None:
    assert infer_slot("L", "性别是女性，生日是三月七号") == ""
