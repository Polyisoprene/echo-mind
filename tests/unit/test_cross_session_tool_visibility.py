"""Cross-chat tools must be visible to the model, not merely registered."""

from __future__ import annotations

from echomind.mind.cybernetics import REAGENT_TOOLS
from echomind.runtime.prompt_composer import VOICE_AND_SPEAK_GUIDE


def test_send_to_chat_is_in_daily_reagent() -> None:
    assert "send_to_chat" in REAGENT_TOOLS["日常轻装剂"]


def test_prompt_mentions_cross_session_target() -> None:
    assert "send_to_chat" in VOICE_AND_SPEAK_GUIDE
    assert "target_chat_key" in VOICE_AND_SPEAK_GUIDE
