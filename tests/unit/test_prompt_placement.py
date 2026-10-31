"""D14: both persona-block placements produce a valid prompt, default stays user."""

from __future__ import annotations

from echomind.domain.models import AffectiveVector, CognitiveFrame, DriveState
from echomind.runtime.prompt_composer import PromptComposer


def _frame() -> CognitiveFrame:
    return CognitiveFrame(
        chat_key="group:1", scene="group", must_reply=False,
        affect=AffectiveVector(), drives=DriveState(),
        rendered_mind_block="【MIND-BLOCK】",
    )


def test_default_keeps_the_dynamic_block_in_the_user_turn() -> None:
    messages = PromptComposer("角色", "回音").compose(_frame(), (), ())
    assert "【MIND-BLOCK】" in messages[1]["content"]
    assert "【MIND-BLOCK】" not in messages[0]["content"]


def test_system_variant_moves_the_block_into_the_system_prompt() -> None:
    composer = PromptComposer("角色", "回音", persona_in_system=True)
    messages = composer.compose(_frame(), (), ())
    assert "【MIND-BLOCK】" in messages[0]["content"]
    assert "【MIND-BLOCK】" not in messages[1]["content"]
