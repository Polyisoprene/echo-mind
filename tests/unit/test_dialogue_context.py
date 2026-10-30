"""Stage 33: probe context must include her own replies, not just inbound messages."""

from __future__ import annotations

from echomind.mind.dialogue_context import DialogueContext


def test_buffer_keeps_both_sides() -> None:
    ctx = DialogueContext()
    ctx.add("L今晚早睡了吗", "你变聪明了吗")
    ctx.add("我", "聪明不聪明，你自己试试不就知道了")
    ctx.add("L今晚早睡了吗", "我该怎么测试呢")
    lines = ctx.lines()
    assert lines[-2].startswith("我: 聪明不聪明")
    assert lines[-1] == "L今晚早睡了吗: 我该怎么测试呢"


def test_note_returns_window_with_new_line() -> None:
    ctx = DialogueContext()
    assert ctx.note("A", "hi") == ("A: hi",)


def test_window_is_bounded_and_truncated() -> None:
    ctx = DialogueContext(limit=3)
    for i in range(6):
        ctx.add("A", f"m{i}")
    assert len(ctx.lines()) == 3 and ctx.lines()[-1] == "A: m5"
    ctx.add("B", "x" * 200)
    assert len(ctx.lines()[-1]) <= 90


def test_blank_lines_are_ignored() -> None:
    ctx = DialogueContext()
    ctx.add("A", "   ")
    assert ctx.lines() == ()
