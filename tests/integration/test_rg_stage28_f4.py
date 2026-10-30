"""Stage 28 RGR-F4: a 6D chord must shift mood exactly once per turn."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept
from echomind.mind import drives as drives_mod
from echomind.mind.subconscious_probe import SubconsciousChordProbe

CK = "group:10002002"
OWNER = "10001001"
PAYLOAD = (
    '{"role":"about_me","topic_pull":3,'
    '"chord":{"joy":3,"hurt":0,"jealousy":0,"shyness":2,"annoyance":0,"curiosity":1},'
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
    ) -> dict[str, Any]:
        _ = (messages, tools, temperature, max_tokens, thinking_off, chat_key)
        return {"choices": [{"message": {"content": PAYLOAD}}]}


def _percept() -> Percept:
    return Percept(
        chat_key=CK, scene="group", message_id="f4-1", timestamp_ms=1_700_000_000_000,
        sender_id="2005", sender_name="冰色", text="回音你今天好乖好可爱，真想摸摸头",
    )


async def test_rg_f4_chord_applied_once(tmp_path: Path, monkeypatch: Any) -> None:
    """A waking turn must apply the chord at exactly one layer (gate xor cognitive frame)."""
    container = await EchoMindContainer.create(
        db_path=tmp_path / "f4.db", operator_ids=(OWNER,), default_chat_key=CK
    )
    facade = container.cognitive_facade
    facade.set_subconscious_probe(SubconsciousChordProbe(_ChordLlm()))

    applications: list[str] = []
    orig_rpe = drives_mod._chord_rpe_and_soothing

    def rpe_spy(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("chord") is not None:
            applications.append("chord")
        return orig_rpe(*args, **kwargs)

    monkeypatch.setattr(drives_mod, "_chord_rpe_and_soothing", rpe_spy)

    percept = _percept()
    dec = await facade.evaluate_incoming(percept)
    assert dec.should_wake is True, "this turn is designed to wake"
    await facade.build_cognitive_frame(CK, (percept,))

    assert len(applications) == 1, (
        f"chord must shift mood exactly once per turn, got {len(applications)} applications"
    )
