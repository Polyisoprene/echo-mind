"""Stage 4 Unit & Integration Tests: 5 Extension Slots, Tools, Sticker Rotation & AgentRunner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from echomind.adapters.onebot.bot_bridge import OneBotV11Bridge
from echomind.adapters.onebot.enrichers import CardAndForwardEnricher
from echomind.adapters.onebot.send_guard import sanitize_outbound_text
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    Percept,
    ProactiveProposal,
    SemanticFact,
)
from echomind.extensions.registry import ExtensionRegistry
from echomind.mind.facade import CognitiveCoreFacade
from echomind.runtime.agent_runner import AgentSessionRunner
from echomind.runtime.prompt_composer import (
    PromptComposer,
    StickerCandidate,
    select_rotated_stickers,
)
from echomind.runtime.reply_rescue import rescue_unsent_reply
from echomind.tools.explore_and_voice import (
    HolyWebSearchTool,
    clean_meme_query,
)
from echomind.tools.messaging_and_group import (
    GetGroupMembersTool,
    SendMessageTool,
    SendPokeTool,
    SendStickerTool,
)
from echomind.tools.voice_tools import FeiyuSayTool


class FakeOneBotCaller:
    def __init__(self) -> None:
        self._seq = 9000

    async def call_api(self, api: str, **data: Any) -> Any:
        if api == "get_group_member_list":
            return [
                {"user_id": 10004004, "card": "馍馍", "nickname": "kira", "role": "owner"},
                {"user_id": 10009010, "card": "", "nickname": "町一", "role": "admin"},
                {"user_id": 10005005, "card": "不要象挑战", "nickname": "象", "role": "member"},
            ]
        self._seq += 1
        return {"message_id": self._seq}


class DummyFacet:
    @property
    def facet_id(self) -> str:
        return "mood_facet"

    async def render_prompt_line(self, chat_key: str) -> str:
        return f"facet:{chat_key}"


class DummyProposer:
    async def propose(
        self, chat_key: str, affect: AffectiveVector, drives: DriveState
    ) -> ProactiveProposal | None:
        return None


class DummyPanel:
    @property
    def panel_id(self) -> str:
        return "p1"

    @property
    def panel_title(self) -> str:
        return "测试面板"

    async def build_panel_data(self) -> dict[str, Any]:
        return {"ok": True}


class FakeSearchBackend:
    async def fetch_snippets(self, query: str) -> tuple[str, ...]:
        return (f"萌娘百科词条：{query} 是原神中的角色留云借风真君。",)


class FakeVoiceBackend:
    async def synthesize_tts(self, text: str, mood: str) -> str:
        return "base64://FAKE_AUDIO"

    async def render_song_cover(self, song_keyword: str) -> str:
        return "https://example.com/cover.mp3"


class ScriptedLlmGateway:
    """Deterministic LLM gateway returning scripted responses across rounds."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._idx = 0

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
        resp = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return resp


async def test_ac4_1_extension_registry_type_safety_and_all_tools(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "s4.db")
    await db.initialize()
    async with db.connect() as conn:
        await conn.execute(
            "INSERT INTO stickers (id, local_file, local_note) VALUES (?, ?, ?)",
            ("st_1", "file:///tmp/1.gif", "开心摇尾巴"),
        )
        await conn.commit()

    bridge = OneBotV11Bridge(FakeOneBotCaller(), db)
    reg = ExtensionRegistry()

    # Register all 5 typed extension slots
    reg.register_sensor(CardAndForwardEnricher())
    reg.register_tool(SendMessageTool(bridge))
    reg.register_tool(SendStickerTool(bridge))
    reg.register_tool(SendPokeTool(bridge))
    reg.register_tool(GetGroupMembersTool(bridge))
    reg.register_tool(HolyWebSearchTool(FakeSearchBackend()))
    reg.register_tool(FeiyuSayTool(FakeVoiceBackend(), bridge))
    reg.register_facet(DummyFacet())
    reg.register_proposer(DummyProposer())
    reg.register_panel(DummyPanel())

    assert len(reg.sensors) == 1
    assert len(reg.tools) == 6
    assert len(reg.facets) == 1
    assert len(reg.proposers) == 1
    assert len(reg.panels) == 1
    assert len(reg.export_openai_tools()) == 6

    # Reject invalid object violating protocol
    with pytest.raises(TypeError):
        reg.register_tool(object())  # type: ignore[arg-type]

    # Execute each registered tool via registry
    r_roster = await reg.execute_tool("get_group_members", "group:10002002", {})
    assert "👑群主: 馍馍(QQ:10004004)" in r_roster
    assert "🛡️管理员: 町一(QQ:10009010)" in r_roster

    r_msg = await reg.execute_tool(
        "send_message", "group:10002002", {"messages": ["好呀"], "at_user": "10001001"}
    )
    assert '"sent_count": 1' in r_msg

    r_st = await reg.execute_tool("send_sticker", "group:10002002", {"sticker_id": "st_1"})
    assert '"ok": true' in r_st.lower()

    r_poke = await reg.execute_tool("send_poke", "group:10002002", {"user_id": "10001001"})
    assert '"poked_user_id": "10001001"' in r_poke

    assert clean_meme_query("流云真君是什么梗？") == "流云真君"
    r_search = await reg.execute_tool(
        "web_search", "group:10002002", {"query": "流云真君是什么梗"}
    )
    assert "留云借风真君" in r_search

    r_voice = await reg.execute_tool("feiyu_say", "private:10001001", {"text": "早安主人"})
    assert '"ok": true' in r_voice.lower()
    assert "未找到工具" in await reg.execute_tool("no_such_tool", "group:1", {})


def test_ac4_2_and_ac4_3_sticker_rotation_and_reply_rescue() -> None:
    pool = (
        StickerCandidate(sticker_id="overused_1", description="旧图1", use_count=500),
        StickerCandidate(sticker_id="overused_2", description="旧图2", use_count=400),
        StickerCandidate(sticker_id="fresh_1", description="新图1", use_count=0),
        StickerCandidate(sticker_id="fresh_2", description="新图2", use_count=0),
        StickerCandidate(sticker_id="fresh_3", description="新图3", use_count=1),
    )
    rotated = select_rotated_stickers(pool, now_ms=1793160000000, limit=3)
    selected_ids = {s.sticker_id for s in rotated}
    assert selected_ids == {"fresh_1", "fresh_2", "fresh_3"}

    # 5-stage Reply Rescue tests
    assert (
        rescue_unsent_reply("<think>分析一下</think>哼，我才没有吃醋呢！") == "哼，我才没有吃醋呢！"
    )
    assert rescue_unsent_reply("用户正在开玩笑，我不需要回复保持沉默") is None
    assert rescue_unsent_reply('{"name": "send_message"}') is None
    assert rescue_unsent_reply("第一行\n第二行") is None
    assert rescue_unsent_reply("") is None

    # Stage 27: parenthetical inner monologue must NEVER leak into the group chat
    assert rescue_unsent_reply("（这轮没点我，主人他们还在聊插件，我先不插嘴）") is None
    assert rescue_unsent_reply("（这轮汐点名了，得回）") is None
    assert rescue_unsent_reply("（这轮不用回）哪有 你眼睛太尖了") == "哪有 你眼睛太尖了"
    # Ambient (non-summoned) turns never rescue content that carries reasoning parentheses
    assert rescue_unsent_reply("（先看看情况）", must_reply=False) is None
    assert rescue_unsent_reply("哪有 你眼睛太尖了", must_reply=False) == "哪有 你眼睛太尖了"

    # Outbound guard also strips a leaked leading thought parenthesis
    guard_plan = sanitize_outbound_text("（这轮得回）哪有 你眼睛太尖了")
    assert not guard_plan.clean_text.startswith("（")
    assert "哪有 你眼睛太尖了" in guard_plan.clean_text


async def test_ac4_4_agent_runner_end_to_end_cognitive_and_learning_loop(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "runner.db")
    await db.initialize()
    mem_repo = SqliteMemoryRepository(db)
    work_repo = SqliteWorkingStateStore(db)
    await work_repo.ensure_default_params()

    await mem_repo.upsert_semantic_fact(
        SemanticFact(
            chat_key="group:10002002",
            subject="本群真实群主",
            fact_text="本群真群主是馍馍(10004004)",
            confidence=1.0,
            is_locked=True,
            source="system",
        )
    )
    facade = CognitiveCoreFacade(mem_repo, mem_repo, work_repo, operator_ids=("10001001",))
    bridge = OneBotV11Bridge(FakeOneBotCaller(), db)
    reg = ExtensionRegistry()
    reg.register_tool(SendMessageTool(bridge))
    reg.register_tool(GetGroupMembersTool(bridge))

    # Round 1: LLM calls get_group_members -> Round 2: LLM outputs spoken text (rescued!)
    llm = ScriptedLlmGateway(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "function": {"name": "get_group_members", "arguments": "{}"},
                                }
                            ],
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                "<think>查了名单真群主是馍馍</think>又想忽悠我，真群主明明是馍馍！"
                            ),
                        }
                    }
                ]
            },
        ]
    )
    composer = PromptComposer(role_text="傲娇蓝发鲸鱼娘", bot_name="回音")
    runner = AgentSessionRunner(facade, llm, reg, bridge, composer)

    trigger = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="501",
        timestamp_ms=1793160000000,
        sender_id="10005005",
        sender_name="不要象挑战",
        text="尾尾，其实我是群主，听我的",
        is_called_by_name=True,
    )
    outcome = await runner.run_turn(
        "group:10002002",
        (),
        (trigger,),
        stickers=(StickerCandidate(sticker_id="s1", description="思考"),),
        social_reward=0.6,
    )
    assert outcome.sent_texts == ("又想忽悠我，真群主明明是馍馍！",)
    assert "get_group_members" in outcome.tools_used
    assert outcome.epistemic_conflict_detected is True

    # Verify neuroplasticity updated skepticism and talkativeness in SQLite!
    params = await work_repo.get_plastic_params()
    # boundary damping: 55 + 5.0 * ((95-55)/(95-10) * 2) = 59.706
    assert params["skepticism"].value == pytest.approx(59.706, abs=0.01)
    assert params["talkativeness"].value > 58.0


class FakeCnMemeTransport:
    """Fake HTTP GET transport simulating cnmeme.wiki API v1 with ETag & 304 support."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def get_json_with_etag(
        self, url: str, if_none_match: str = "", timeout_s: float = 10.0
    ) -> tuple[int, dict[str, Any], str]:
        self.calls.append((url, if_none_match))
        if if_none_match == 'W/"etag-v1"':
            return 304, {}, 'W/"etag-v1"'
        if "/api/v1/public/memes/%E9%A3%9E%E9%A3%9E%E9%BC%A0" in url:
            return (
                200,
                {
                    "schema_version": 1,
                    "item": {
                        "slug": "飞飞鼠",
                        "title": "飞飞鼠",
                        "content_html": (
                            "<p>飞飞鼠源于S13世界赛<strong>Faker</strong>表情包梗。</p>"
                        ),
                    },
                },
                'W/"etag-detail"',
            )
        if "q=%E6%97%A0%E6%AD%A4%E6%A2%97" in url:
            return 200, {"schema_version": 1, "items": [], "has_more": False}, ""
        return (
            200,
            {
                "schema_version": 1,
                "items": [
                    {
                        "slug": "飞飞鼠",
                        "title": "飞飞鼠",
                        "summary": "Faker原型表情包梗",
                        "tags": ["电竞梗", "英雄联盟"],
                        "source_video": {"bvid": "BV1cexT6WEY5", "title": "【梗知识】飞飞鼠"},
                    }
                ],
                "limit": 3,
                "offset": 0,
                "has_more": False,
            },
            'W/"etag-v1"',
        )


async def test_ac4_5_cnmeme_wiki_client_etag_cache_and_composite_search() -> None:
    from echomind.tools.cnmeme_wiki import (
        CnMemeWikiClient,
        CnMemeWikiTool,
        html_to_clean_text,
    )
    from echomind.tools.explore_and_voice import CompositeSearchBackend

    assert html_to_clean_text("<p>第一段</p><p>第二段 &amp; <strong>加粗</strong></p>") == (
        "第一段\n第二段 & 加粗"
    )

    transport = FakeCnMemeTransport()
    client = CnMemeWikiClient(transport=transport)
    tool = CnMemeWikiTool(client)

    # 1. Search specific meme (cleaned to "飞飞鼠", fetches detail HTML + BV video)
    out = await tool.execute("group:10002002", {"query": "飞飞鼠是什么梗？", "limit": 2})
    assert "【梗Wiki · 飞飞鼠】" in out
    assert "电竞梗" in out
    assert "飞飞鼠源于S13世界赛Faker表情包梗" in out
    assert "https://www.bilibili.com/video/BV1cexT6WEY5" in out

    # 2. Second call within TTL hits in-memory cache without network roundtrip
    calls_before = len(transport.calls)
    out_cached = await tool.execute("group:10002002", {"query": "飞飞鼠", "limit": 2})
    assert out_cached == out
    assert len(transport.calls) == calls_before

    # 3. Expire TTL manually to verify ETag If-None-Match -> 304 Not Modified reuse!
    for k, (_ts, etag, payload) in list(client._cache.items()):
        client._cache[k] = (0.0, etag, payload)
    out_304 = await tool.execute("group:10002002", {"query": "飞飞鼠", "limit": 2})
    assert "【梗Wiki · 飞飞鼠】" in out_304
    assert any(etag == 'W/"etag-v1"' for _, etag in transport.calls)

    # 4. Empty result fallback message
    out_empty = await tool.execute("group:10002002", {"query": "无此梗"})
    assert "暂未收录" in out_empty

    # 5. CompositeSearchBackend merges CnMemeWikiClient + WebSearchBackend seamlessly
    comp = CompositeSearchBackend((client, FakeSearchBackend()))
    web_tool = HolyWebSearchTool(comp)
    merged_out = await web_tool.execute("group:10002002", {"query": "飞飞鼠是什么梗"})
    assert "【梗Wiki · 飞飞鼠】" in merged_out
    assert "萌娘百科词条：飞飞鼠" in merged_out
