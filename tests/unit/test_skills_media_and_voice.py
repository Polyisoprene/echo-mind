"""Media perception & voice skills: image, video, TTS and voice transcription."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from echomind.adapters.media.feiyu import FeiyuVoiceBackend
from echomind.adapters.media.vision import OpenAiVisionDescriber
from echomind.adapters.onebot.media_gateway import OneBotMediaGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import GatewayEndpointConfig
from echomind.domain.models import MediaAttachment
from echomind.tools.media_vision import LookAtImageTool, WatchVideoTool
from echomind.tools.voice_tools import FeiyuSayTool, ReadVoiceTool


class FakeMediaGateway:
    def __init__(self, item: MediaAttachment | None = None, frames: tuple[str, ...] = ()) -> None:
        self._item = item
        self._frames = frames
        self.captions: dict[str, str] = {}

    async def newest_media(self, chat_key: str, kind: str) -> MediaAttachment | None:
        return self._item

    async def load_data_url(self, item: MediaAttachment) -> str:
        return "data:image/png;base64,AAAA"

    async def video_frame_urls(self, item: MediaAttachment, count: int) -> tuple[str, ...]:
        return self._frames

    async def voice_to_text(self, item: MediaAttachment) -> str:
        return "主人晚安"

    async def cache_media_description(self, item: MediaAttachment, caption: str) -> None:
        self.captions[item.local_path] = caption


class FakeVision:
    def __init__(self, reply: str = "图里是一只小白象") -> None:
        self.reply = reply
        self.calls: list[tuple[str, ...]] = []

    async def describe(self, image_urls: tuple[str, ...], prompt: str) -> str:
        self.calls.append(image_urls)
        return self.reply


class FakeVoiceBackend:
    async def synthesize_tts(self, text: str, mood: str) -> str:
        return "QUJD"


class FakeSender:
    """Minimal IMessageSender stub recording voice sends."""

    def __init__(self) -> None:
        self.voices: list[tuple[str, str]] = []

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
        return None

    async def send_voice(self, chat_key: str, audio_b64: str, summary_text: str) -> str | None:
        self.voices.append((chat_key, summary_text))
        return "mid_1"

    async def send_poke(self, chat_key: str, target_user_id: str) -> bool:
        return True


async def test_acX1_look_at_image_and_watch_video() -> None:
    item = MediaAttachment(kind="image", url="http://x/a.jpg")
    vision = FakeVision()
    look = LookAtImageTool(FakeMediaGateway(item), vision)
    assert look.category == "媒体感知"
    assert "小白象" in await look.execute("group:1", {})

    empty = LookAtImageTool(FakeMediaGateway(None), FakeVision())
    assert "没有找到" in await empty.execute("group:1", {})

    video_item = MediaAttachment(kind="video_frames", url="http://x/v.mp4")
    watch = WatchVideoTool(
        FakeMediaGateway(video_item, ("data:image/jpeg;base64,AAA",)), FakeVision("视频里在放烟花")
    )
    assert "烟花" in await watch.execute("group:1", {"frames": 2})
    no_frames = WatchVideoTool(FakeMediaGateway(video_item, ()), FakeVision())
    assert "抽帧失败" in await no_frames.execute("group:1", {})


async def test_acX2_voice_speak_and_transcribe() -> None:
    sender = FakeSender()
    say = FeiyuSayTool(FakeVoiceBackend(), sender)
    assert say.category == "语音表达"
    assert await say.execute("private:1", {"text": "早安"}) != ""
    assert sender.voices == [("private:1", "早安")]
    assert "为空" in await say.execute("private:1", {"text": "  "})

    voice_item = MediaAttachment(kind="voice", message_id="m1")
    read = ReadVoiceTool(FakeMediaGateway(voice_item, ()))
    assert "主人晚安" in await read.execute("group:1", {})
    assert "没有找到" in await ReadVoiceTool(FakeMediaGateway(None)).execute("group:1", {})


class _FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None, content: bytes = b"") -> None:
        self._payload = payload or {}
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    """Minimal httpx.AsyncClient stand-in for deterministic adapter tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.timeout = None

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def post(self, url: str, headers: Any = None, json: Any = None) -> _FakeResponse:
        if url.endswith("/chat/completions"):
            return _FakeResponse({"choices": [{"message": {"content": " 一只猫 "}}]})
        return _FakeResponse({"id": "job_1"})

    async def get(self, url: str, headers: Any = None) -> _FakeResponse:
        if url.endswith("/audio"):
            return _FakeResponse(content=b"WAVDATA")
        return _FakeResponse({"status": "success"})


async def test_acX3_feiyu_tts_and_vision_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("echomind.adapters.media.feiyu.httpx.AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr("echomind.adapters.media.vision.httpx.AsyncClient", _FakeAsyncClient)

    backend = FeiyuVoiceBackend("http://gpu:9880/", "key", poll_interval_s=0.0)
    audio = await backend.synthesize_tts("早安", "温柔")
    assert audio == "V0FWREFUQQ=="

    endpoint = GatewayEndpointConfig(name="P", base_url="http://gw/v1", api_key="k", model="m")
    describer = OpenAiVisionDescriber(endpoint)
    assert await describer.describe(("data:image/png;base64,AA",), "看图") == "一只猫"
    assert await describer.describe((), "看图") == ""


async def test_acX4_media_gateway_reads_newest_attachment(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "media.db")
    await db.initialize()

    class _Caller:
        async def call_api(self, api: str, **data: Any) -> Any:
            return {"text": "语音转写结果"}

    gateway = OneBotMediaGateway(db, _Caller())
    assert await gateway.newest_media("group:1", "image") is None

    async with db.connect() as conn:
        await conn.execute(
            "INSERT INTO chat_messages "
            "(chat_key, mid, ts, sender_id, sender_name, is_self, text, media_json) "
            "VALUES (?,?,?,?,?,0,?,?)",
            (
                "group:1",
                "m1",
                1,
                "u1",
                "群友",
                "[图片]",
                '[{"kind":"image","url":"http://x/a.png","message_id":"m1"}]',
            ),
        )
        await conn.commit()

    item = await gateway.newest_media("group:1", "image")
    assert item is not None and item.url == "http://x/a.png"
    assert (
        await gateway.voice_to_text(MediaAttachment(kind="voice", message_id="m9"))
        == "语音转写结果"
    )
    assert await gateway.voice_to_text(MediaAttachment(kind="voice")) == ""


def test_style_normalization_maps_to_service_supported_values() -> None:
    from echomind.adapters.media.feiyu import normalize_style

    assert normalize_style("可爱") == "cute"
    assert normalize_style("撒娇") == "cute"
    assert normalize_style("温柔") == "gentle"
    assert normalize_style("cute") == "cute"
    assert normalize_style("GENTLE") == "gentle"
    assert normalize_style("乱填的") == "cute"
    assert normalize_style("乱填的", default="gentle") == "gentle"
    assert normalize_style("乱填的", default="也乱填") == "cute"


async def test_voice_health_service_reports_capabilities(tmp_path: Path) -> None:
    from echomind.core.bootstrap import EchoMindContainer
    from echomind.web.voice_health_service import VoiceHealthService

    container = await EchoMindContainer.create(db_path=tmp_path / "vh.db")

    offline = await VoiceHealthService(container).probe()
    assert offline["online"] is False and "未装配" in offline["reason"]

    class _Backend:
        calls = 0

        async def capabilities(self) -> dict[str, Any]:
            _Backend.calls += 1
            return {
                "tts": [
                    {
                        "voice": "feiyu",
                        "engine": "cosyvoice3_release",
                        "available": True,
                        "styles": ["cute", "gentle"],
                        "package_id": "FeiyuVoice-1.0.1",
                    }
                ]
            }

        async def health(self) -> dict[str, Any]:
            return {"status": "ok"}

    container.voice_backend = _Backend()  # type: ignore[assignment]
    service = VoiceHealthService(container)
    first = await service.probe()
    assert first["online"] is True
    assert first["voices"][0]["styles"] == ["cute", "gentle"]
    # 20 秒内走缓存，不重复打服务
    await service.probe()
    assert _Backend.calls == 1

    class _Broken:
        async def capabilities(self) -> dict[str, Any]:
            raise RuntimeError("连接超时")

        async def health(self) -> dict[str, Any]:
            return {}

    container.voice_backend = _Broken()  # type: ignore[assignment]
    broken = await VoiceHealthService(container).probe()
    assert broken["online"] is False and "连接超时" in broken["reason"]


async def test_skill_config_store_and_service_masking(tmp_path: Path) -> None:
    from echomind.adapters.media.bili import BiliClient, build_cookie, mixin_key, sign_params
    from echomind.adapters.storage.skill_config_repo import SqliteSkillConfigStore
    from echomind.core.bootstrap import EchoMindContainer
    from echomind.tools.bili import BiliSearchTool
    from echomind.web.skill_config_service import SkillConfigService

    assert len(mixin_key("a" * 64)) == 32
    signed = sign_params({"keyword": "梗"}, "i" * 32, "s" * 32, ts=1700000000)
    assert "w_rid=" in signed and "wts=1700000000" in signed
    assert build_cookie("S", "J", "U") == "SESSDATA=S; bili_jct=J; DedeUserID=U"

    container = await EchoMindContainer.create(db_path=tmp_path / "cfg.db")
    store = SqliteSkillConfigStore(container.db)
    container.skill_config_store = store
    container.registry.register_tool(BiliSearchTool(BiliClient()))

    service = SkillConfigService(container)
    listed = await service.list_configs()
    bili = next(c for c in listed if c["skill"] == "bili")
    assert [f["key"] for f in bili["fields"]] == ["sessdata", "bili_jct", "dedeuserid"]
    assert bili["values"]["sessdata"] == ""

    await service.save("bili", {"sessdata": "abcdef1234567890", "unknown_key": "x"})
    saved = await store.get_skill_config("bili")
    assert saved["sessdata"] == "abcdef1234567890"
    assert "unknown_key" not in saved

    masked = next(c for c in await service.list_configs() if c["skill"] == "bili")
    assert "…" in masked["values"]["sessdata"]

    # 回传掩码占位符不应覆盖真实值
    await service.save("bili", {"sessdata": "abcd…7890"})
    assert (await store.get_skill_config("bili"))["sessdata"] == "abcdef1234567890"


class _FakeBiliResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeBiliClient:
    """Mimics httpx.AsyncClient for api.bilibili.com."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeBiliClient:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def get(self, url: str, headers: Any = None) -> _FakeBiliResponse:
        if "/x/web-interface/nav" in url:
            return _FakeBiliResponse(
                {
                    "data": {
                        "wbi_img": {
                            "img_url": "https://i0.hdslb.com/bfs/wbi/" + "i" * 32 + ".png",
                            "sub_url": "https://i0.hdslb.com/bfs/wbi/" + "s" * 32 + ".png",
                        }
                    }
                }
            )
        if "wbi/search/type" in url:
            return _FakeBiliResponse(
                {
                    "data": {
                        "result": [
                            {
                                "title": 'AI<em class="keyword">字幕</em>测试',
                                "author": "UP主A",
                                "play": 1234,
                                "duration": "3:05",
                                "bvid": "BV1xx411c7mD",
                            }
                        ]
                    }
                }
            )
        if "/x/web-interface/view" in url:
            return _FakeBiliResponse(
                {
                    "data": {
                        "title": "视频标题",
                        "owner": {"name": "UP主B"},
                        "duration": 185,
                        "stat": {"view": 999, "like": 88, "danmaku": 7},
                        "desc": "简介内容",
                    }
                }
            )
        return _FakeBiliResponse(
            {
                "data": {
                    "list": [
                        {
                            "title": "热门1",
                            "owner": {"name": "UP主C"},
                            "stat": {"view": 555},
                            "bvid": "BVhot",
                        }
                    ]
                }
            }
        )


async def test_bili_client_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from echomind.adapters.media.bili import BiliClient
    from echomind.tools.bili import BiliPopularTool, BiliSearchTool, BiliVideoTool

    monkeypatch.setattr("echomind.adapters.media.bili.httpx.AsyncClient", _FakeBiliClient)

    async def cookies() -> dict[str, str]:
        return {"sessdata": "SD", "bili_jct": "JCT", "dedeuserid": "42"}

    client = BiliClient(cookie_provider=cookies)
    headers = await client._headers()
    assert headers["Cookie"] == "SESSDATA=SD; bili_jct=JCT; DedeUserID=42"

    found = await BiliSearchTool(client).execute("group:1", {"keyword": "AI", "limit": 3})
    assert "AI字幕测试" in found and "BV1xx411c7mD" in found
    assert "3:05" in found

    info = await BiliVideoTool(client).execute("group:1", {"bvid": "BV1xx411c7mD"})
    assert "视频标题" in info and "UP主B" in info and "3:05" in info

    hot = await BiliPopularTool(client).execute("group:1", {"limit": 3})
    assert "热门1" in hot and "555" in hot

    assert "为空" in await BiliSearchTool(client).execute("group:1", {})
    assert "缺少 bvid" in await BiliVideoTool(client).execute("group:1", {})

    # 无 cookie 的客户端
    plain = BiliClient()
    assert (await plain._headers()).get("Cookie") is None


async def test_skill_toggle_delete_restore_and_memory_consolidator(tmp_path: Path) -> None:
    from echomind.adapters.storage.skill_config_repo import SqliteSkillConfigStore
    from echomind.core.bootstrap import EchoMindContainer
    from echomind.domain.models import Percept, TurnOutcome
    from echomind.mind.memory_consolidator import (
        consolidate_turn_memory,
        run_hippocampal_batch_consolidation,
    )
    from echomind.mind.plasticity import compute_turn_social_reward
    from echomind.mind.subconscious_probe import SubconsciousChordResult
    from echomind.web.skill_config_service import SkillConfigService

    assert compute_turn_social_reward("拍一拍", is_poke=True) == 0.55
    assert (
        compute_turn_social_reward(
            is_owner=True, chord=SubconsciousChordResult(joy=3)
        )
        > 0.5
    )
    assert (
        compute_turn_social_reward(
            is_owner=True, chord=SubconsciousChordResult(annoyance=2, hurt=1)
        )
        < -0.4
    )

    container = await EchoMindContainer.create(db_path=tmp_path / "toggle.db")
    container.skill_config_store = SqliteSkillConfigStore(container.db)
    svc = SkillConfigService(container)

    res1 = await svc.toggle_tool("web_search")
    assert res1["enabled"] is False
    assert "技能 web_search 已在控制台被禁用" in await container.registry.execute_tool(
        "web_search", "group:1", {}
    )

    res2 = await svc.toggle_tool("web_search")
    assert res2["enabled"] is True

    await svc.delete_tool("web_search")
    assert "web_search" in container.registry.deleted_tools
    restored = await svc.restore_deleted()
    assert "web_search" in restored["restored"]
    assert "web_search" not in container.registry.deleted_tools

    trig = Percept(
        chat_key="group:1",
        scene="group",
        message_id="m100",
        timestamp_ms=1793200000000,
        sender_id="10001001",
        sender_name="主人",
        text="记住我喜欢吃草莓蛋糕",
        is_at_me=True,
    )
    outcome = TurnOutcome(
        session_id="s100",
        chat_key="group:1",
        triggers=(trig,),
        sent_texts=("记好啦，主人最喜欢草莓蛋糕",),
        tools_used=("send_message",),
        social_reward=0.6,
    )
    await consolidate_turn_memory(
        container.memory_repo,
        container.memory_repo,
        outcome,
        1793200001000,
        ("10001001",),
        chord=SubconsciousChordResult(explicit_fact="我喜欢吃草莓蛋糕"),
    )
    facts = await container.memory_repo.get_semantic_facts("group:1")
    bond = await container.memory_repo.get_social_bond("group:1", "10001001")
    assert len(facts) == 1 and "草莓蛋糕" in facts[0].fact_text
    assert bond is not None and bond.affinity_score > 30.0
    async with container.db.connect() as conn:
        row = await (await conn.execute("SELECT last_seen_ms FROM social_bonds")).fetchone()
    assert row is not None and row[0] > 0  # last_seen_ms is persisted
    assert bond.group_role == "admin"

    class _FakeConsolidateLlm:
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
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"cards":[{"summary":"主人和回音约定吃草莓蛋糕并织蓝色围巾",'
                                '"keyDetail":"草莓蛋糕、蓝色围巾","participants":["10001001"],'
                                '"importance":4.5,"pinned":true}],"facts":[],"rules":[],"newPersonaTrait":""}'
                            )
                        }
                    }
                ]
            }

    n_cards = await run_hippocampal_batch_consolidation(
        "group:1",
        container.memory_repo,
        container.memory_repo,
        _FakeConsolidateLlm(),
        ("a: 1", "b: 2", "c: 3", "d: 4"),
        now_ms=1793200002000,
    )
    assert n_cards == 1


async def test_persona_card_hot_reload_and_bidirectional_affinity(tmp_path: Path) -> None:
    from echomind.adapters.onebot.live_client import _filter_fresh_batch
    from echomind.core.bootstrap import EchoMindContainer
    from echomind.domain.models import Percept
    from echomind.mind.memory_consolidator import compute_affinity_delta
    from echomind.runtime.prompt_composer import PromptComposer
    from echomind.web.llm_config_service import LlmConfigService

    p_pos = Percept(
        chat_key="group:1",
        scene="group",
        message_id="m1",
        timestamp_ms=1_000_000,
        sender_id="1001",
        sender_name="甲",
        text="回音你今天真的太棒太可爱啦，谢谢你织的围巾",
        is_at_me=True,
    )
    p_neg = Percept(
        chat_key="group:1",
        scene="group",
        message_id="m2",
        timestamp_ms=900_000,
        sender_id="1001",
        sender_name="甲",
        text="闭嘴真烦",
    )
    # Positive gain with diminishing returns at higher base_score
    gain_low = compute_affinity_delta(p_pos, 20.0, 0.7)
    gain_high = compute_affinity_delta(p_pos, 400.0, 0.7)
    assert gain_low > gain_high > 0.0
    # Negative delta when scolded or spoofing conflict detected
    assert compute_affinity_delta(p_neg, 120.0, -0.6) < -2.0
    assert compute_affinity_delta(p_pos, 120.0, 0.5, conflict=True) == -6.0

    # Stale trigger drop (>45s old)
    fresh = _filter_fresh_batch([p_neg, p_pos], now_ms=1_010_000)
    assert fresh == (p_pos,)

    # Base persona card hot-reload
    cfg_file = tmp_path / "cfg.json"
    cfg_file.write_text(
        '{"persona":{"botName":"回音","roleText":"初始小鲸鱼设定"}}', encoding="utf-8"
    )
    container = await EchoMindContainer.create(db_path=tmp_path / "p.db")
    container.prompt_composer = PromptComposer(role_text="初始小鲸鱼设定", bot_name="回音")
    svc = LlmConfigService(container, cfg_file)
    assert svc.read_persona()["role_text"] == "初始小鲸鱼设定"
    updated = svc.apply_persona("尾尾", "更新后的最初人设")
    assert updated["applied"] is True and updated["bot_name"] == "尾尾"
    assert container.prompt_composer.role_card() == ("尾尾", "更新后的最初人设")
    from echomind.web.mind_inspector_service import MindInspectorService

    insp = MindInspectorService(container)
    tuned = await insp.update_social_bond(
        "1001", 260.0, chat_key="group:1", user_name="甲", is_rival=True
    )
    assert tuned["ok"] is True
    assert tuned["bond"]["affinity_score"] == 260.0
    assert tuned["bond"]["affinity_level"] == 5
    assert tuned["bond"]["is_rival"] is True
    from echomind.tools.member_memory import RememberMemberTool

    rm = RememberMemberTool(container.memory_repo, container.memory_repo)
    out = await rm.execute(
        "group:1", {"user_id": "10005005", "user_name": "不要象挑战", "content": "外号叫毛玉老师"}
    )
    assert "毛玉老师" in out
    assert rm.name == "memory_append" and rm.description != ""
    assert "user_id" in rm.parameters_schema()["properties"]
    assert "缺少" in await rm.execute("group:1", {})


def test_at_other_member_preserved_and_ignored_by_gate() -> None:
    from echomind.adapters.onebot.event_parser import parse_onebot_event
    from echomind.domain.models import WorkingSnapshot
    from echomind.mind.perceptual_gate import PerceptualGate

    ev = {
        "post_type": "message",
        "message_type": "group",
        "group_id": 10002002,
        "user_id": 10001001,
        "message_id": 999,
        "time": 1793200000,
        "sender": {"card": "L今晚早睡了吗"},
        "message": [
            {"type": "at", "data": {"qq": "10007007", "name": "汐"}},
            {"type": "text", "data": {"text": " 你怎么看"}},
        ],
    }
    parsed = parse_onebot_event(ev, "10003003", frozenset({"10002002"}), ("10001001",))
    assert parsed is not None
    assert parsed.is_at_me is False
    assert "@汐(QQ:10007007)" in parsed.text

    gate = PerceptualGate()
    # Even if the sender is in the 5-minute followup window, @other_member must NOT wake the bot
    gate.mark_replied_to("group:10002002", "10001001", 1793200000 * 1000)
    dec = gate.evaluate(parsed, WorkingSnapshot(scope_key="global"))
    assert dec.should_wake is False
    assert "艾特其他群友" in dec.reason


async def test_qzone_tools_and_showcase_scheduler(tmp_path: Path) -> None:
    from echomind.adapters.storage.skill_config_repo import SqliteSkillConfigStore
    from echomind.core.bootstrap import EchoMindContainer
    from echomind.runtime.qzone_scheduler import QzoneMoodShowcaseScheduler, is_within_active_hours
    from echomind.tools.qzone_and_profile import ProfileSignatureTool, QzonePublishTool

    # 12:00 CST = 04:00 UTC -> timestamp_ms = 4 * 3600 * 1000
    noon_cst_ms = 1_793_160_000_000
    assert is_within_active_hours("06:30-23:30", noon_cst_ms) is True

    class _QzoneCaller:
        async def call_api(self, api: str, **data: Any) -> Any:
            return {"tid": "t1"}

    caller = _QzoneCaller()
    qz_tool = QzonePublishTool(caller)
    sig_tool = ProfileSignatureTool(caller)
    assert len(qz_tool.config_fields()) == 16
    assert "ok" in await qz_tool.execute(
        "group:1", {"content": "今天阳光真好", "visibility": "public"}
    )
    assert "ok" in await sig_tool.execute("group:1", {"signature": "抱着尾巴晒太阳"})

    container = await EchoMindContainer.create(db_path=tmp_path / "qz.db")
    cfg_store = SqliteSkillConfigStore(container.db)
    await cfg_store.set_skill_config(
        "qzone_showcase",
        {
            "signature_enabled": "1",
            "signature_per_day": "3",
            "signature_interval_min": "60",
            "qzone_enabled": "1",
            "qzone_per_day": "5",
            "qzone_interval_min": "60",
            "active_hours": "00:00-23:59",
        },
    )

    class _FakeQzoneLlm:
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
            return {"choices": [{"message": {"content": "晒着太阳晃尾巴，今天慢慢来"}}]}

    from echomind.adapters.onebot.bot_bridge import OneBotV11Bridge

    sched = QzoneMoodShowcaseScheduler(
        caller=caller,
        llm=_FakeQzoneLlm(),
        working_store=container.working_store,
        memory_reader=container.memory_repo,
        config_store=cfg_store,
        default_chat_key="group:1",
        sender=OneBotV11Bridge(caller, container.db),
    )
    executed = await sched.run_tick(noon_cst_ms)
    assert "signature" in executed and "qzone" in executed and "proactive" in executed
    # Immediately ticking again within interval_min should be a no-op
    assert await sched.run_tick(noon_cst_ms + 1000) == {}

    # Cover empty/error/cross-midnight branches of qzone tools and scheduler
    assert "未发布" in await qz_tool.execute("group:1", {"content": ""})
    assert "未修改" in await sig_tool.execute("group:1", {"signature": ""})
    assert is_within_active_hours("22:00-02:00", noon_cst_ms) is False
    assert is_within_active_hours("", noon_cst_ms) is True
    assert is_within_active_hours("bad:spec", noon_cst_ms) is True
    assert qz_tool.name == "qzone_showcase" and sig_tool.name == "qzone_showcase"
    assert "content" in qz_tool.parameters_schema()["properties"]
    assert "content" in sig_tool.parameters_schema()["properties"]
    assert qz_tool.description != "" and sig_tool.description != ""

    from echomind.domain.models import TurnOutcome
    from echomind.mind.frame_renderer import _energy_directive
    from echomind.mind.personality import derive_emergent_trait

    assert "精力充沛" in _energy_directive(80.0)
    assert "精力平稳" in _energy_directive(50.0)
    assert "精力偏低" in _energy_directive(25.0)
    assert "极度困倦" in _energy_directive(10.0)
    t_img = derive_emergent_trait(
        TurnOutcome(session_id="s1", chat_key="group:1", triggers=(), tools_used=("look_at_image",))
    )
    t_tts = derive_emergent_trait(
        TurnOutcome(session_id="s2", chat_key="group:1", triggers=(), tools_used=("feiyu_say",))
    )
    assert t_img is not None and t_tts is not None
