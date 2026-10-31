"""Trace backfill uses real assistant outputs and one context per UTC day."""

from __future__ import annotations

import json

from echomind.mind.trait_trace_backfill import candidates_from_rows


def _row(turn_id: str, ts: int, output: str) -> dict[str, object]:
    steps = [
        {"kind": "tool", "name": "look_at_image", "output": ""},
        {"kind": "llm", "output": output},
        {"kind": "tool", "name": "send_message",
         "detail": json.dumps({"rescued": output}, ensure_ascii=False)},
    ]
    return {"turn_id": turn_id, "chat_key": "g", "ts": ts,
            "steps_json": json.dumps(steps, ensure_ascii=False)}


def test_one_latest_quote_per_day_and_existing_day_skipped() -> None:
    day = 86_400_000
    rows = [
        _row("a", 1 * day + 10, "旧输出"),
        _row("b", 1 * day + 20, "当天最新输出"),
        _row("c", 1 * day + 30, ""),
        _row("d", 2 * day + 10, "第二天输出"),
        _row("e", 3 * day + 10, "已有 context 的日子"),
    ]
    result = candidates_from_rows(rows, existing_days={3})
    assert [item.turn_id for item in result] == ["b", "d"]
    assert result[0].quote == "当天最新输出"
    assert result[1].quote == "第二天输出"


def test_no_llm_output_is_not_fabricated() -> None:
    row = {"turn_id": "x", "chat_key": "g", "ts": 1,
           "steps_json": json.dumps([{"kind": "tool", "name": "look_at_image"}])}
    assert candidates_from_rows([row], existing_days=set()) == ()


def test_sent_message_text_beats_internal_thought() -> None:
    steps = [
        {"kind": "llm", "output": "（内心独白，不发出）"},
        {"kind": "tool", "name": "send_message", "detail": '{"rescued": "实际发出的话"}'},
    ]
    row = {
        "turn_id": "s", "chat_key": "g", "ts": 1,
        "steps_json": json.dumps(steps, ensure_ascii=False),
    }
    result = candidates_from_rows([row], existing_days=set())
    assert result[0].quote == "实际发出的话"
