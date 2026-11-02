"""BDI intentions must reach the model through the rendered mind block."""

from __future__ import annotations

from echomind.domain.models import IntentionItem, WorkingSnapshot
from echomind.mind.frame_renderer import render_mind_block


def test_unfinished_commitment_is_rendered() -> None:
    snap = WorkingSnapshot(
        scope_key="global",
        intentions=(IntentionItem(
            summary="我这就去群里说", created_at_ms=1, expires_at_ms=0,
            target_chat_key="group:1",
        ),),
    )
    block = render_mind_block(
        "group", snap, facts=(), warnings=(), shadow_directives=(),
        rule_lines=[], recalled=(), cur_prompts=(),
    )
    assert "短期挂念" in block
    assert "我这就去群里说" in block
    assert "group:1" in block
