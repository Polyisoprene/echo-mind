"""Sticker selection: mood-aware ranking, anti-Matthew rotation and send cooldown."""

from __future__ import annotations

import json
from typing import Any

from echomind.domain.models import AffectiveVector
from echomind.runtime.prompt_composer import (
    StickerCandidate,
    preferred_tags,
    select_rotated_stickers,
)
from echomind.tools.messaging_and_group import SendStickerTool


class _StickerSender:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(
        self,
        chat_key: str,
        messages: tuple[str, ...],
        reply_to_mid: str | None = None,
        at_user_id: str | None = None,
    ) -> tuple[str, ...]:
        return ()

    async def send_sticker(
        self, chat_key: str, sticker_id: str, reply_to_mid: str | None = None
    ) -> str | None:
        self.sent.append(sticker_id)
        return f"mid_{len(self.sent)}"

    async def send_voice(self, chat_key: str, audio_b64: str, summary_text: str) -> str | None:
        return None

    async def send_poke(self, chat_key: str, target_user_id: str) -> bool:
        return True


def test_preferred_tags_follow_affect() -> None:
    assert "开心" in preferred_tags(AffectiveVector(valence=80.0))
    assert "嫌弃" in preferred_tags(AffectiveVector(irritation=60.0))
    assert "委屈" in preferred_tags(AffectiveVector(jealousy=40.0))
    assert "害羞" in preferred_tags(AffectiveVector(shyness=60.0))
    assert "发呆" in preferred_tags(AffectiveVector(energy=20.0))
    assert preferred_tags(AffectiveVector()) <= {"卖萌"}


def test_mood_matching_sticker_outranks_popular_one() -> None:
    popular = StickerCandidate(
        sticker_id="pop", description="常用卖萌图", use_count=60, tags=("卖萌",)
    )
    moodfit = StickerCandidate(sticker_id="fit", description="嫌弃脸", use_count=0, tags=("嫌弃",))
    picked = select_rotated_stickers(
        (popular, moodfit), now_ms=1_700_000_000_000, mood_tags=frozenset({"嫌弃"})
    )
    assert picked[0].sticker_id == "fit"

    without_mood = select_rotated_stickers((popular, moodfit), now_ms=1_700_000_000_000)
    assert without_mood[0].sticker_id == "fit"

    assert select_rotated_stickers((StickerCandidate(sticker_id="x", description="  "),), 0) == ()


async def test_sticker_cooldown_blocks_rapid_resend() -> None:
    sender = _StickerSender()
    tool = SendStickerTool(sender, cooldown_ms=30_000)
    first = json.loads(await tool.execute("group:1", {"sticker_id": "a"}))
    assert first["ok"] is True
    assert sender.sent == ["a"]

    blocked: Any = await tool.execute("group:1", {"sticker_id": "b"})
    assert "刚发过表情包" in blocked
    assert sender.sent == ["a"]

    # 不同群互不影响
    assert json.loads(await tool.execute("group:2", {"sticker_id": "c"}))["ok"] is True
    assert sender.sent == ["a", "c"]
