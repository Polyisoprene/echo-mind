"""Stage 29 A4: prompts must follow the configured persona name, not a literal one."""

from __future__ import annotations

from echomind.mind.naming import BotNaming, bot_naming, set_bot_naming
from echomind.mind.personality import synthesize_live_persona_directive
from echomind.mind.subconscious_probe import build_probe_system_prompt


def test_probe_prompt_uses_configured_name() -> None:
    set_bot_naming(BotNaming(name="星野", aliases=("小星",)))
    try:
        prompt = build_probe_system_prompt()
        assert "星野" in prompt and "小星" in prompt
        assert "回音" not in prompt and "尾尾" not in prompt
    finally:
        set_bot_naming(BotNaming())


def test_personality_block_heading_follows_name() -> None:
    set_bot_naming(BotNaming(name="星野"))
    try:
        block = synthesize_live_persona_directive({}, ())
        assert "星野" in block and "回音" not in block
    finally:
        set_bot_naming(BotNaming())


def test_default_naming_is_echo() -> None:
    assert bot_naming().label() == "回音"
