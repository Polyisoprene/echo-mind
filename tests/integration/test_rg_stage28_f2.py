"""Stage 28 RGR-F2: a direct-summon turn must still obtain a 6D chord (no emotional blind spot)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept
from echomind.mind.subconscious_probe import SubconsciousChordProbe

CK = "group:10002002"
OWNER = "10001001"
PAYLOAD = (
    '{"role":"direct_to_me","topic_pull":2,'
    '"chord":{"joy":3,"hurt":0,"jealousy":0,"shyness":2,"annoyance":0,"curiosity":0},'
    '"shadow_trigger":"none","spoof_attempt":false,"explicit_fact":"",'
    '"reagents":["日常轻装剂"],"shade":"被主人夸得耳根发烫","subtext":"主人真心的","thought":"嘿嘿"}'
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
    ) -> dict[str, Any]:
        _ = (messages, tools, temperature, max_tokens, thinking_off, chat_key)
        return {"choices": [{"message": {"content": PAYLOAD}}]}


async def test_rg_f2_tier1_turn_gets_chord(tmp_path: Path) -> None:
    """An @-summoned owner turn skips the gate probe, so the frame must fetch the chord."""
    container = await EchoMindContainer.create(
        db_path=tmp_path / "f2.db", operator_ids=(OWNER,), default_chat_key=CK
    )
    facade = container.cognitive_facade
    facade.set_subconscious_probe(SubconsciousChordProbe(_ChordLlm()))

    percept = Percept(
        chat_key=CK, scene="group", message_id="f2-1", timestamp_ms=1_700_000_000_000,
        sender_id=OWNER, sender_name="主人", text="尾尾今天真乖真好看", is_at_me=True,
    )
    dec = await facade.evaluate_incoming(percept)
    assert dec.tier == 1 and dec.should_wake is True
    assert percept.message_id not in facade._chord_cache, "gate skips tier-1 probing"

    frame = await facade.build_cognitive_frame(CK, (percept,))
    assert percept.message_id in facade._chord_cache, "frame must resolve the missing chord"
    assert frame.affect.shyness > 0, "owner praise must still move shyness"
