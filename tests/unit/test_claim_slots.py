"""Slot inference is conservative and only marks person traits."""

from __future__ import annotations

from echomind.mind.claim_slots import infer_slot, is_single


def test_nickname_is_multi_valued() -> None:
    assert infer_slot("L", "L的群昵称是「小L」") == ""
    assert not is_single("person.nickname")


def test_qq_is_single() -> None:
    slot = infer_slot("L", "QQ号是 123456789")
    assert slot == "person.qq"
    assert is_single(slot)


def test_preference_is_not_a_slot() -> None:
    assert infer_slot("L", "L喜欢吃草莓蛋糕") == ""


def test_mentioned_and_experience_are_not_slots() -> None:
    assert infer_slot("L", "L提到今天在忙") == ""
    assert infer_slot("L", "L在玩格斗游戏") == ""


def test_ambiguous_match_returns_empty() -> None:
    assert infer_slot("L", "性别是女性，生日是三月七号") == ""


def test_meta_subjects_are_never_person_slots() -> None:
    assert infer_slot("自组织图式:外号", "围绕外号聚合的2段经历") == ""
    assert infer_slot("本群真实群主", "群主的外号是馍馍") == ""


def test_gender_is_not_owner() -> None:
    assert infer_slot("L", "主人是男的") == ""


def test_computer_city_is_not_a_city() -> None:
    assert infer_slot("菲菲", "住在主人电脑里的鲸鱼娘") == ""


def test_group_id_is_not_a_slot() -> None:
    assert not is_single("person.group_id")
    assert infer_slot("L", "群内ID是 12345") == ""
