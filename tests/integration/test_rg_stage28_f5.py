"""Stage 28 RGR-F5: chord-driven ambient wakes must honour the 75s cooldown window."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept
from echomind.mind.subconscious_probe import SubconsciousChordProbe

CK = "group:10002002"
OWNER = "10001001"
PAYLOAD = (
    '{"role":"about_me","topic_pull":3,'
    '"chord":{"joy":3,"hurt":0,"jealousy":0,"shyness":1,"annoyance":0,"curiosity":1},'
    '"shadow_trigger":"none","spoof_attempt":false,"explicit_fact":"",'
    '"reagents":["日常轻装剂"],"shade":"被夸得耳根发烫","subtext":"在夸我","thought":"嘿嘿"}'
)


class _ChordLlm:
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.6,
        max_tokens: int = 800,
        thinking_off: bool = False,
        *,
        chat_key: str = "",
        json_mode: bool = False,
        model_override: str = "",
        tool_choice: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = (messages, tools, temperature, max_tokens, thinking_off, chat_key)
        return {"choices": [{"message": {"content": PAYLOAD}}]}


def _percept(mid: str, ts: int) -> Percept:
    return Percept(
        chat_key=CK, scene="group", message_id=mid, timestamp_ms=ts,
        sender_id="2005", sender_name="冰色", text="回音你今天真的好乖好可爱呀，辛苦了",
    )


async def test_rg_f5_cooldown_not_bypassed(tmp_path: Path) -> None:
    """Two chord-driven ambient wakes within 75s: the second must be cooled down."""
    container = await EchoMindContainer.create(
        db_path=tmp_path / "f5.db", operator_ids=(OWNER,), default_chat_key=CK
    )
    facade = container.cognitive_facade
    facade.set_subconscious_probe(SubconsciousChordProbe(_ChordLlm()))

    first = await facade.evaluate_incoming(_percept("f5-1", 1_700_000_000_000))
    second = await facade.evaluate_incoming(_percept("f5-2", 1_700_000_005_000))

    assert first.should_wake is True, "the first praise turn should wake"
    assert second.should_wake is False, "a second ambient wake inside 75s must be suppressed"
    assert "冷却" in second.reason, f"expected cooldown reason, got {second.reason}"
