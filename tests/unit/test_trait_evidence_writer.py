"""Evidence quote priority: assistant text > tool > user trigger."""

from __future__ import annotations

from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.trait_evidence_writer import trait_quote


def _outcome(*, sent: tuple[str, ...] = (), tools: tuple[str, ...] = ()) -> TurnOutcome:
    percept = Percept(
        chat_key="g", scene="group", message_id="m", timestamp_ms=1,
        sender_id="u", sender_name="U", text="trigger",
    )
    return TurnOutcome(
        session_id="s", chat_key="g", triggers=(percept,), sent_texts=sent,
        tools_used=tools,
    )


def test_assistant_text_wins() -> None:
    assert trait_quote(_outcome(sent=("reply",), tools=("look_at_image",))) == (
        "assistant", "reply",
    )


def test_tool_wins_over_trigger_when_no_reply() -> None:
    assert trait_quote(_outcome(tools=("look_at_image",))) == (
        "tool", "look_at_image",
    )


def test_trigger_is_last_resort() -> None:
    assert trait_quote(_outcome()) == ("user", "trigger")
