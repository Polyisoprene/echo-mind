"""Stage 28 RGR-F1: production-path reward parity for chord-driven learning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.plasticity import compute_turn_social_reward
from echomind.mind.subconscious_probe import SubconsciousChordProbe

CK = "group:10002002"
OWNER = "10001001"


class _ChordLlm:
    """Minimal ILlmGateway stub returning one fixed subconscious chord payload."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

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
        return {"choices": [{"message": {"content": self._payload}}]}


def _chord_payload(annoyance: int, joy: int) -> str:
    return (
        '{"role":"ambient_daily","topic_pull":2,'
        f'"chord":{{"joy":{joy},"hurt":0,"jealousy":0,"shyness":0,'
        f'"annoyance":{annoyance},"curiosity":1}},'
        '"shadow_trigger":"none","spoof_attempt":false,"explicit_fact":"",'
        '"reagents":["日常轻装剂"],"shade":"测试染色","subtext":"测试潜台词","thought":"测试内心OS"}'
    )


def _percept(uid: str, text: str) -> Percept:
    return Percept(
        chat_key=CK, scene="group", message_id=f"rg-{uid}", timestamp_ms=1_700_000_000_000,
        sender_id=uid, sender_name=f"用户{uid}", text=text,
    )


async def _run_turn(
    db_path: Path, uid: str, text: str, payload: str
) -> float:
    """Drive the exact production path: gate probe -> on_turn_completed -> bond trust."""
    container = await EchoMindContainer.create(
        db_path=db_path, owner_qq=OWNER, default_chat_key=CK
    )
    facade = container.cognitive_facade
    facade.set_subconscious_probe(SubconsciousChordProbe(_ChordLlm(payload)))
    percept = _percept(uid, text)
    await facade.evaluate_incoming(percept)
    # Parity with live_client: reward is derived from text only at the call site.
    reward = compute_turn_social_reward(text, is_poke=False, is_owner=False)
    await facade.on_turn_completed(
        TurnOutcome(
            session_id=f"rg-{uid}", chat_key=CK, triggers=(percept,),
            sent_texts=("哼",), social_reward=reward,
        )
    )
    bond = await container.memory_repo.get_social_bond(CK, uid)
    assert bond is not None
    return bond.trust_score


async def test_rg_f1_production_reward_not_constant(tmp_path: Path) -> None:
    """F1: an insulting turn must lower trust while a praising turn raises it."""
    insult = await _run_turn(
        tmp_path / "f1a.db", "2005", "你这蠢AI，快给我闭嘴，别在这儿烦人", _chord_payload(3, 0)
    )
    praise = await _run_turn(
        tmp_path / "f1b.db", "2006", "你今天真好看，特别乖，谢谢你陪我聊天", _chord_payload(0, 3)
    )
    assert insult < 0.75, f"insult turn must lose trust, got {insult}"
    assert praise > 0.75, f"praise turn must gain trust, got {praise}"
    assert praise - insult > 0.02, f"reward must vary by semantics, got {praise - insult}"


