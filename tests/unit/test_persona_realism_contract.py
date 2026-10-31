"""The persona directive carries the human-realism contract."""

from __future__ import annotations

from echomind.mind.personality import synthesize_live_persona_directive


def test_directive_has_realism_contract() -> None:
    text = synthesize_live_persona_directive({}, ())
    assert "真人感硬约束" in text
    assert "26 字" in text
    assert "不解释人设和规则" in text
