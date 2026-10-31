"""Stage 33: probe context must include her own replies, not just inbound messages."""

from __future__ import annotations

from echomind.mind.dialogue_context import DialogueContext


def test_buffer_keeps_both_sides() -> None:
    ctx = DialogueContext()
    ctx.add("g", "L今晚早睡了吗", "你变聪明了吗")
    ctx.add("g", "我", "聪明不聪明，你自己试试不就知道了")
    ctx.add("g", "L今晚早睡了吗", "我该怎么测试呢")
    lines = ctx.lines("g")
    assert lines[-2].startswith("我: 聪明不聪明")
    assert lines[-1] == "L今晚早睡了吗: 我该怎么测试呢"


def test_note_returns_window_with_new_line() -> None:
    ctx = DialogueContext()
    assert ctx.note("g", "A", "hi") == ("A: hi",)


def test_window_is_bounded_and_truncated() -> None:
    ctx = DialogueContext(limit=3)
    for i in range(6):
        ctx.add("g", "A", f"m{i}")
    assert len(ctx.lines("g")) == 3 and ctx.lines("g")[-1] == "A: m5"
    ctx.add("g", "B", "x" * 200)
    assert len(ctx.lines("g")[-1]) <= 90


def test_blank_lines_are_ignored() -> None:
    ctx = DialogueContext()
    ctx.add("g", "A", "   ")
    assert ctx.lines("g") == ()


def test_scopes_do_not_see_each_other() -> None:
    ctx = DialogueContext()
    ctx.add("group:1", "A", "群里的秘密")
    ctx.add("private:L", "L", "私聊的话")
    assert ctx.lines("group:1") == ("A: 群里的秘密",)
    assert ctx.lines("private:L") == ("L: 私聊的话",)
