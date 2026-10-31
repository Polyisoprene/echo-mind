"""Stage 31 S31-2: bot belief is extracted from natural-language facts."""

from __future__ import annotations

from echomind.mind.bot_belief import apply_belief, rebuild, score_fact, set_beliefs


def test_fact_with_qq_and_keyword_yields_belief() -> None:
    got = score_fact("菲菲", "菲菲(QQ:10009009)是机器人，不要频繁接她的话", 1.0)
    assert got["10009009"] >= 0.8


def test_fact_without_keyword_is_ignored() -> None:
    assert score_fact("菲菲", "菲菲喜欢咕噜", 1.0) == {}


def test_conflicting_facts_take_the_strongest() -> None:
    facts = (
        ("菲菲", "菲菲是机器人", 0.5),
        ("菲菲", "菲菲(QQ:10009009)是机器人，会刷屏，少接", 1.0),
    )
    merged = rebuild(facts)
    assert merged["10009009"] >= 0.8


def test_beliefs_are_bounded_and_applied() -> None:
    set_beliefs("group:1", {"10009009": 3.0})
    assert apply_belief("group:1", "10009009") == 1.0
    assert apply_belief("group:1", "999") == 0.0
    set_beliefs("group:1", {})


def test_beliefs_do_not_leak_across_chats() -> None:
    set_beliefs("group:1", {"10009009": 1.0})
    set_beliefs("group:2", {})
    assert apply_belief("group:1", "10009009") == 1.0
    assert apply_belief("group:2", "10009009") == 0.0


def test_an_id_in_the_name_is_not_confused_with_another_nickname() -> None:
    got = score_fact("汐", "汐(QQ:3993173948)是机器人", 1.0)
    assert "3993173948" in got
    assert "10009009" not in got


def test_building_a_bot_is_not_being_a_bot() -> None:
    """阿斋想自己搭建一个机器人 → 不能因此判定阿斋是机器人。"""
    fact = "阿斋想自己搭建一个『鲸鱼娘』机器人，打算参考B站教程动手做。"
    assert score_fact("阿斋(QQ:908424192)", fact, 0.85) == {}


def test_aggregate_summaries_are_not_assertions() -> None:
    """自组织图式是聚合摘要，不能当成"某人是机器人"的证据。"""
    assert score_fact("自组织图式:官方机器人", "忆染(QQ:812896023)问L今晚早睡了吗", 0.86) == {}
