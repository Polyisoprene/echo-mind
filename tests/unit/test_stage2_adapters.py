"""Stage 2 Unit, Integration & Hypothesis Fuzz Tests: OneBot Bridge, Enrichers, GIF Codec & LLM."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st
from PIL import Image

from echomind.adapters.llm.anchor import PrefixAnchorEngine
from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.onebot.bot_bridge import OneBotV11Bridge
from echomind.adapters.onebot.enrichers import (
    CardAndForwardEnricher,
    ImageCaptionCacheEnricher,
    PerceptEnrichmentPipeline,
    QuoteStickerEnricher,
)
from echomind.adapters.onebot.media_codec import gif_to_storyboard_data_url
from echomind.adapters.onebot.send_guard import OutboundDeduplicator, sanitize_outbound_text
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import GatewayEndpointConfig
from echomind.domain.models import MediaAttachment, Percept
from echomind.domain.ports import (
    IGroupRosterReader,
    ILlmGateway,
    IMessageSender,
    IPerceptEnricher,
)


class FakeOneBotCaller:
    """Test double satisfying IOneBotApiCaller (LSP)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._seq = 9000

    async def call_api(self, api: str, **data: Any) -> Any:
        self.calls.append((api, data))
        if api == "get_group_member_list":
            return [
                {"user_id": 10004004, "card": "馍馍", "nickname": "kira", "role": "owner"},
                {"user_id": 10009010, "card": "", "nickname": "町一", "role": "admin"},
                {"user_id": 10005005, "card": "不要象挑战", "nickname": "象", "role": "member"},
            ]
        self._seq += 1
        return {"message_id": self._seq}


class FakeHttpTransport:
    """Test double satisfying IHttpPostTransport with configurable primary failure."""

    def __init__(self, fail_primary: bool = False) -> None:
        self.fail_primary = fail_primary
        self.called_urls: list[str] = []

    async def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_s: float
    ) -> dict[str, Any]:
        self.called_urls.append(url)
        if self.fail_primary and "9000" in url:
            raise RuntimeError("Primary gateway HTTP 502")
        return {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 800},
            },
        }


def test_m2_1_anti_double_at_and_quote_merge_guard() -> None:
    # 1. Both at_user_id and "@昵称" in text -> strip "@昵称" and prepend single space
    plan1 = sanitize_outbound_text("@凤歌储油人 包子头吉祥", at_user_id="10008008")
    assert plan1.clean_text == " 包子头吉祥"
    assert plan1.effective_at_uid == "10008008"

    # 2. Both reply_to_mid and at_user_id -> drop redundant at_user_id
    plan2 = sanitize_outbound_text(
        "[CQ:at,qq=10008008] @凤歌(QQ:10008008)：好呀",
        reply_to_mid="1001",
        at_user_id="10008008",
    )
    assert plan2.clean_text == "好呀"
    assert plan2.effective_reply_mid == "1001"
    assert plan2.effective_at_uid is None

    # 3. No native @ or reply -> keep text intact
    plan3 = sanitize_outbound_text("你好呀")
    assert plan3.clean_text == "你好呀"
    assert plan3.effective_at_uid is None

    # 4. Sliding-window deduplicator
    dedup = OutboundDeduplicator(window_ms=5000)
    assert not dedup.is_duplicate("group:1", "在的", now_ms=1000)
    assert dedup.is_duplicate("group:1", "在的", now_ms=3000)
    assert not dedup.is_duplicate("group:1", "在的", now_ms=7000)


@given(body=st.text(min_size=1, max_size=40).filter(lambda s: not s.strip().startswith("@")))
def test_m2_1_sanitize_outbound_property_fuzz(body: str) -> None:
    raw = f"@测试群友(QQ:123456) {body}"
    plan = sanitize_outbound_text(raw, at_user_id="123456")
    assert not plan.clean_text.strip().startswith("@测试群友")
    assert plan.effective_at_uid == "123456"


async def test_m2_1_and_m2_2_onebot_bridge_and_enricher_pipeline(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "stage2.db")
    await db.initialize()

    # Seed a sticker and an MD5 image caption
    async with db.connect() as conn:
        await conn.execute(
            "INSERT INTO stickers (id, local_file, local_note) VALUES (?, ?, ?)",
            ("collected_188", "file:///tmp/whale.gif", "蓝白小鲸鱼皱眉深度思考中"),
        )
        await conn.execute(
            "INSERT INTO image_caption_cache (md5, description) VALUES (?, ?)",
            ("ABC123MD5", "白毛少女比心表情"),
        )
        await conn.commit()

    caller = FakeOneBotCaller()
    bridge = OneBotV11Bridge(caller, db)
    assert isinstance(bridge, IMessageSender)
    assert isinstance(bridge, IGroupRosterReader)

    # Send text, sticker, voice, poke, and query group roster
    mids = await bridge.send_text(
        "group:10002002", ("@凤歌 包子头吉祥", "第二句"), at_user_id="10008008"
    )
    assert len(mids) == 2
    sticker_mid = await bridge.send_sticker("group:10002002", "collected_188", reply_to_mid="50")
    assert sticker_mid == "9003"
    assert await bridge.send_sticker("group:10002002", "missing_id") is None
    voice_mid = await bridge.send_voice("private:10001001", "AAAA", "早安")
    assert voice_mid == "9004"
    assert await bridge.send_poke("group:10002002", "10001001")
    assert await bridge.send_poke("private:10001001", "10001001")

    roster = await bridge.get_group_members("10002002")
    assert len(roster) == 3
    assert roster[0].group_role == "owner" and roster[0].user_name == "馍馍"
    assert roster[1].group_role == "admin"

    with pytest.raises(ValueError):
        await bridge.send_text("bad_key", ("hi",))

    # Test M2.2 PerceptEnrichmentPipeline (QuoteSticker + Card + ImageCaptionCache)
    q_enricher = QuoteStickerEnricher(db)
    c_enricher = CardAndForwardEnricher()
    i_enricher = ImageCaptionCacheEnricher(db)
    assert isinstance(q_enricher, IPerceptEnricher)
    pipeline = PerceptEnrichmentPipeline((q_enricher, c_enricher, i_enricher))

    raw_percept = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="9999",
        timestamp_ms=1793160000000,
        sender_id="10001001",
        sender_name="L今晚早睡了吗",
        text="尾尾，你发的这是群主形象",
        quoted_message_id="9003",
        quoted_text="[image]",
        media=(MediaAttachment(kind="image", local_path="abc123md5"),),
    )
    enriched = await pipeline.process(raw_percept)
    assert enriched.is_called_by_name is True
    assert enriched.is_quoted_me is True
    assert "蓝白小鲸鱼皱眉深度思考中" in enriched.quoted_text
    assert enriched.quoted_text.startswith("#9003")
    assert enriched.media[0].description == "白毛少女比心表情"

    # Test mini-app JSON card enrichment
    card_percept = raw_percept.model_copy(
        update={
            "quoted_message_id": "",
            "text": '{"prompt":"[哔哩哔哩]","meta":{"detail_1":{"title":"流云真君PV","qqdocurl":"https://b23.tv/xyz"}}}',
        }
    )
    enriched_card = await pipeline.process(card_percept)
    assert "流云真君PV" in enriched_card.text and "https://b23.tv/xyz" in enriched_card.text


def test_m2_2_gif_to_storyboard_data_url() -> None:
    assert gif_to_storyboard_data_url(b"") == ""
    frames = [
        Image.new("RGBA", (64, 64), (255, 0, 0, 255)),
        Image.new("RGBA", (64, 64), (0, 255, 0, 255)),
        Image.new("RGBA", (64, 64), (0, 0, 255, 255)),
    ]
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], loop=0)
    data_url = gif_to_storyboard_data_url(buf.getvalue())
    assert data_url.startswith("data:image/jpeg;base64,")
    assert len(data_url) > 500


async def test_m2_3_failover_llm_gateway_and_prefix_anchor(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "llm.db")
    await db.initialize()
    prim = GatewayEndpointConfig(
        name="WorkBuddy", base_url="http://127.0.0.1:9000/v1", api_key="k1", model="m1"
    )
    fall = GatewayEndpointConfig(
        name="dsh-ntr", base_url="http://127.0.0.1:9914/v1", api_key="k2", model="m2"
    )

    # 1. Primary succeeds
    t_ok = FakeHttpTransport(fail_primary=False)
    gw1 = FailoverLlmGateway(prim, fall, db, transport=t_ok)
    assert isinstance(gw1, ILlmGateway)
    r1 = await gw1.complete([{"role": "user", "content": "hi"}])
    assert r1["choices"][0]["message"]["content"] == "ok"
    assert len(t_ok.called_urls) == 1 and "9000" in t_ok.called_urls[0]

    # 2. Primary fails -> automatic failover to dsh-ntr (9914)
    t_fail = FakeHttpTransport(fail_primary=True)
    gw2 = FailoverLlmGateway(prim, fall, db, transport=t_fail)
    r2 = await gw2.complete([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    assert r2["choices"][0]["message"]["content"] == "ok"
    assert len(t_fail.called_urls) == 2 and "9914" in t_fail.called_urls[1]

    # Verify traces recorded in SQLite
    async with db.connect() as conn:
        cursor = await conn.execute(
            "SELECT gateway_name, is_failover, cached_tokens FROM llm_traces"
        )
        rows = list(await cursor.fetchall())
        assert len(rows) == 2
        assert rows[0][0] == "WorkBuddy" and rows[0][1] == 0 and rows[0][2] == 800
        assert rows[1][0] == "dsh-ntr" and rows[1][1] == 1

    # 3. PrefixAnchorEngine test
    engine = PrefixAnchorEngine(max_extra_read=4, window_size=10)
    assert engine.resolve("group:1", (), ("u1",)).mode == "reset"

    d1 = engine.resolve("group:1", (1, 2, 3, 4, 5, 6, 7, 8), ("u1", "u2"))
    assert d1.mode == "reset"

    # Incremental read within max_extra_read & same members -> anchored!
    d2 = engine.resolve("group:1", (1, 2, 3, 4, 5, 6, 7, 8, 9), ("u1",))
    assert d2.mode == "anchored"
    assert d2.anchored_ids == d1.anchored_ids
    assert 9 in d2.extra_ids

    # Exceed max_extra_read -> reset!
    d3 = engine.resolve("group:1", tuple(range(1, 20)), ("u1",))
    assert d3.mode == "reset"


async def test_ac2_6_local_sticker_is_inlined_as_base64(tmp_path: Path) -> None:
    """NapCat 在容器里读不到宿主机路径，本地表情必须内联成 base64 才能发出去。"""
    db = SqliteDatabase(tmp_path / "sticker.db")
    await db.initialize()
    sticker_file = tmp_path / "whale.png"
    sticker_file.write_bytes(b"\x89PNG\r\n\x1a\nFAKEBYTES")
    async with db.connect() as conn:
        await conn.execute(
            "INSERT INTO stickers (id, local_file, local_note) VALUES (?, ?, ?)",
            ("s_local", f"file://{sticker_file}", "本地测试表情"),
        )
        await conn.commit()

    caller = FakeOneBotCaller()
    bridge = OneBotV11Bridge(caller, db)
    mid = await bridge.send_sticker("group:10002002", "s_local")
    assert mid is not None

    send_calls = [data for api, data in caller.calls if api == "send_group_msg"]
    assert send_calls, "应当真的调用了 send_group_msg"
    image_seg = next(s for s in send_calls[-1]["message"] if s["type"] == "image")
    assert image_seg["data"]["file"].startswith("base64://")

    # 不存在的本地文件保持原样，交给协议端自行报错
    async with db.connect() as conn:
        await conn.execute(
            "INSERT INTO stickers (id, local_file, local_note) VALUES (?, ?, ?)",
            ("s_missing", "file:///no/such/sticker.png", "缺失文件"),
        )
        await conn.commit()
    await bridge.send_sticker("group:10002002", "s_missing")
    last = [data for api, data in caller.calls if api == "send_group_msg"][-1]
    seg = next(s for s in last["message"] if s["type"] == "image")
    assert seg["data"]["file"] == "file:///no/such/sticker.png"
