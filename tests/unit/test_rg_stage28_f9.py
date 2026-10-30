"""Stage 28 RGR-F9: subconscious context must never leak across chats."""

from __future__ import annotations

from echomind.mind.chord_gateway import format_recent


def test_rg_f9_recent_ctx_scoped() -> None:
    gate_log = [
        {"chat_key": "group:A", "sender_name": "甲", "text": "A 群第一句"},
        {"chat_key": "group:B", "sender_name": "乙", "text": "B 群私密话"},
        {"chat_key": "group:A", "sender_name": "丙", "text": "A 群第二句"},
    ]
    scoped = format_recent(gate_log, "group:A")
    assert "B 群" not in " ".join(scoped), f"cross-chat leak: {scoped}"
    assert len(scoped) == 2
    assert format_recent(gate_log, "group:B") == ("乙: B 群私密话",)
