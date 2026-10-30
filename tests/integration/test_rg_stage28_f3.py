"""Stage 28 RGR-F3: a message burst must not trigger one probe per message."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept
from echomind.mind.subconscious_probe import SubconsciousChordProbe

CK = "group:10002002"
OWNER = "10001001"
PAYLOAD = (
    '{"role":"ambient_daily","topic_pull":1,'
    '"chord":{"joy":0,"hurt":0,"jealousy":0,"shyness":0,"annoyance":0,"curiosity":0},'
    '"shadow_trigger":"none","spoof_attempt":false,"explicit_fact":"",'
    '"reagents":["日常轻装剂"],"shade":"平静旁听","subtext":"普通闲聊","thought":"听着呢"}'
)


class _CountingLlm:
    def __init__(self) -> None:
        self.calls = 0

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
        self.calls += 1
        return {"choices": [{"message": {"content": PAYLOAD}}]}


async def test_rg_f3_probe_once_per_batch(tmp_path: Path) -> None:
    """Four ambient messages inside two seconds must cost at most two probes."""
    container = await EchoMindContainer.create(
        db_path=tmp_path / "f3.db", owner_qq=OWNER, default_chat_key=CK
    )
    facade = container.cognitive_facade
    llm = _CountingLlm()
    probe = SubconsciousChordProbe(llm)
    facade.set_subconscious_probe(probe)

    base = 1_700_000_000_000
    for idx in range(4):
        percept = Percept(
            chat_key=CK, scene="group", message_id=f"f3-{idx}", timestamp_ms=base + idx * 800,
            sender_id="2005", sender_name="冰色", text=f"今天群里聊的东西还挺多的第{idx}条",
        )
        await facade.evaluate_incoming(percept)

    assert llm.calls <= 2, f"burst must be coalesced, got {llm.calls} probe calls"
