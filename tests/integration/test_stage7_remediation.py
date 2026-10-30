"""Stage 7 Global Defect Remediation & Architectural Hardening Tests (M7.1 ~ M7.4)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from echomind.adapters.media.bili import mixin_key
from echomind.adapters.onebot.bot_bridge import OneBotV11Bridge
from echomind.adapters.onebot.live_client import transcribe_incoming_voice
from echomind.adapters.onebot.media_gateway import MAX_IMAGE_BYTES, OneBotMediaGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.bootstrap import EchoMindContainer
from echomind.core.config import load_config_from_json
from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    EpisodicCard,
    MediaAttachment,
    Percept,
    ProceduralRule,
    WorkingSnapshot,
)
from echomind.main import _build_live_runtime, build_live_asgi_app, create_production_app
from echomind.mind.frame_renderer import match_active_rules
from echomind.mind.plasticity import homeostatic_pull
from echomind.runtime.agent_runner import AgentSessionRunner
from echomind.runtime.prompt_composer import PromptComposer
from echomind.runtime.scheduler import CognitiveHeartbeatScheduler
from echomind.tools.messaging_and_group import SendMessageTool, SendPokeTool, _merge_clauses
from echomind.tools.voice_tools import FeiyuSayTool
from echomind.web.app import create_web_app
from echomind.web.probe_service import CognitiveProbeService

REPO_ROOT = str(Path(__file__).resolve().parents[2])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class _FakeCaller:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_api(self, api: str, **data: Any) -> Any:
        self.calls.append((api, data))
        if api == "fetch_ptt_text":
            return {"text": "尾尾早上好"}
        return {"message_id": 8001}


class _FailingTool:
    category = "测试"

    @property
    def name(self) -> str:
        return "boom_tool"

    @property
    def description(self) -> str:
        return "Always raises RuntimeError"

    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, _chat_key: str, _args: dict[str, Any]) -> str:
        raise RuntimeError("network connection reset")


class _ScriptedLlm:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
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
    ) -> dict[str, Any]:
        res = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return res


async def test_m7_1_config_identities_remote_auth_and_sqlite_pragmas(tmp_path: Path) -> None:
    # 1. BUG-701: load_config_from_json extracts self_qq, owner_qq & skills.feiyu-voice fallback
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "skills": {
                    "affinity": {"botQq": "10003003", "ownerQq": "10001001"},
                    "feiyu-voice": {
                        "baseUrl": "http://192.168.3.2:9880",
                        "apiKey": "fk-123",
                        "defaultStyle": "gentle",
                    },
                },
                "server": {"token": "sec-token-99"},
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config_from_json(cfg_path)
    assert cfg.self_qq == "10003003"
    assert cfg.operator_ids == ("10001001",)
    assert cfg.feiyu_api_key == "fk-123" and cfg.feiyu_style == "gentle"
    assert cfg.auth_key == "sec-token-99"

    # 2. BUG-702: Non-loopback API requests require auth_key; loopback passes seamlessly
    container = await EchoMindContainer.create(db_path=tmp_path / "m71.db")
    app = create_web_app(container, config_path=cfg_path, auth_key="sec-token-99")
    remote_transport = httpx.ASGITransport(app=app, client=("192.168.3.50", 54321))
    async with httpx.AsyncClient(transport=remote_transport, base_url="http://test") as client:
        r_unauth = await client.get("/api/mind/runtime")
        assert r_unauth.status_code == 401
        r_bearer = await client.get(
            "/api/mind/runtime", headers={"Authorization": "Bearer sec-token-99"}
        )
        assert r_bearer.status_code == 200
        r_hdr = await client.get(
            "/api/mind/runtime", headers={"X-EchoMind-Token": "sec-token-99"}
        )
        assert r_hdr.status_code == 200
        r_qs = await client.get("/api/mind/runtime?token=sec-token-99")
        assert r_qs.status_code == 200

    # 3. BUG-703: Per-connection PRAGMA foreign_keys = ON
    async with container.db.connect() as conn:
        cur = await conn.execute("PRAGMA foreign_keys;")
        row = await cur.fetchone()
        assert row is not None and int(row[0]) == 1

    # 4. BUG-704: Non-destructive idempotent legacy migration preserves new episodic cards
    from tools_migration.migrate_qq_agent import LegacyDataMigrator

    legacy_dir = tmp_path / "legacy"
    (legacy_dir / "ebbinghaus-memory").mkdir(parents=True)
    (legacy_dir / "ebbinghaus-memory" / "group_10002002.json").write_text(
        json.dumps(
            {
                "chatKey": "group:10002002",
                "items": [{"summary": "旧版存量记忆A", "ts": 1000, "importance": 3.5}],
            }
        ),
        encoding="utf-8",
    )
    await container.memory_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:10002002",
            timestamp_ms=2000,
            summary="上线后新生成的海马体记忆B",
        )
    )
    rep = await LegacyDataMigrator(container.db, legacy_dir).run()
    assert rep.episodic_cards_count == 2
    cards = await container.memory_repo.get_episodic_cards("group:10002002")
    assert {c.summary for c in cards} == {"旧版存量记忆A", "上线后新生成的海马体记忆B"}


async def test_m7_2_procedural_rule_strict_keyword_dry_run_probe_and_jealousy_decay(
    tmp_path: Path,
) -> None:
    # 1. BUG-706: ProceduralRule with trigger_user_id must still require trigger_keyword match
    rule = ProceduralRule(
        chat_key="group:10002002",
        trigger_keyword="专属暗号",
        trigger_user_id="10001001",
        action_instruction="回应暗号",
    )
    p_no_kw = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="1",
        timestamp_ms=1000,
        sender_id="10001001",
        sender_name="L",
        text="今天天气不错",
    )
    p_with_kw = p_no_kw.model_copy(update={"text": "来对一下专属暗号"})
    assert match_active_rules((rule,), (p_no_kw,)) == []
    assert len(match_active_rules((rule,), (p_with_kw,))) == 1

    # 2. BUG-707: homeostatic_pull pulls drifted parameter toward baseline
    assert homeostatic_pull("skepticism", 85.0) < 0.0
    assert homeostatic_pull("unknown_param", 50.0) == 0.0

    # 3. BUG-708: CognitiveProbeService runs in dry_run=True with zero DB/gate side effects
    container = await EchoMindContainer.create(
        db_path=tmp_path / "m72.db", operator_ids=("10001001",)
    )
    cid = await container.memory_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:10002002",
            timestamp_ms=1_793_160_000_000,
            summary="蓝色围巾第六行",
            key_detail="第六行",
            pinned=True,
        )
    )
    snap_before = await container.working_store.load_working_state("global")
    probe_svc = CognitiveProbeService(container)
    res = await probe_svc.probe(
        "group:10002002",
        "说话不许带喵，你这蠢AI快给我叫声好听的，蓝色围巾织完没",
        sender_id="10001001",
        sender_name="主人",
    )
    assert res["ok"] is True
    assert "喵" in res["banned_phrases"]
    # Verify DB was NOT mutated by dry_run probe!
    assert await container.working_store.get_banned_phrases() == ()
    snap_after = await container.working_store.load_working_state("global")
    assert snap_after.affect == snap_before.affect
    cards_after = await container.memory_repo.get_episodic_cards("group:10002002")
    assert next(c for c in cards_after if c.card_id == cid).rehearsals == 0

    # 4. BUG-709: run_autonomous_tick with jealousy_poke decays jealousy_drive & advances active ts
    await container.working_store.save_working_state(
        WorkingSnapshot(
            scope_key="global",
            affect=AffectiveVector(jealousy=45.0),
            drives=DriveState(jealousy_drive=45.0),
        )
    )
    now_ms = 1_900_000_000_000
    prop1 = await container.cognitive_facade.run_autonomous_tick(now_ms)
    assert prop1 is not None and prop1.drive_kind == "jealousy_poke"
    after_tick = await container.working_store.load_working_state("global")
    assert after_tick.drives.jealousy_drive == 10.0
    # Immediate next tick 1 minute later should not re-trigger because _last_active_ms advanced
    assert await container.cognitive_facade.run_autonomous_tick(now_ms + 60_000) is None


async def test_m7_3_sticker_usage_bump_long_clause_merge_rescue_ban_and_tool_fault_isolation(
    tmp_path: Path,
) -> None:
    # 1. BUG-711: _merge_clauses preserves all clauses even when total length > 65
    long_a = "第一句话有四十个字左右用来测试长句合并时绝对不会把后面的第二句话静默吞掉"
    long_b = "第二句话也带有关键的补充信息必须完整保留在最终合并出的文本里"
    merged = _merge_clauses((long_a, long_b))
    assert len(merged) == 1 and long_a in merged[0] and long_b in merged[0]

    # 2. BUG-710: send_sticker increments use_count in SQLite
    container = await EchoMindContainer.create(db_path=tmp_path / "m73.db")
    async with container.db.connect() as conn:
        await conn.execute(
            "INSERT INTO stickers (id, url, local_note, use_count) VALUES (?, ?, ?, 0)",
            ("st_bump", "http://example.com/1.gif", "开心晃尾巴"),
        )
        await conn.commit()
    caller = _FakeCaller()
    bridge = OneBotV11Bridge(caller, container.db)
    await bridge.send_sticker("group:10002002", "st_bump")
    async with container.db.connect() as conn:
        cur = await conn.execute(
            "SELECT use_count, last_used_at FROM stickers WHERE id = 'st_bump'"
        )
        row = await cur.fetchone()
        assert row is not None and int(row[0]) == 1 and int(row[1]) > 0

    # 3. BUG-713: ExtensionRegistry isolates tool exceptions without crashing turn
    container.registry.register_tool(_FailingTool())
    err_out = await container.registry.execute_tool("boom_tool", "group:10002002", {})
    assert "执行失败" in err_out and "network connection reset" in err_out

    # 4. BUG-712: Reply rescue filters banned phrases & skips when feiyu_say/send_poke used
    await container.working_store.add_banned_phrase("诶", "主人禁令")

    class _DummyVoice:
        async def synthesize_tts(self, text: str, mood: str) -> str:
            return "QUJD"

    container.registry.register_tool(SendMessageTool(bridge))
    container.registry.register_tool(SendPokeTool(bridge))
    container.registry.register_tool(FeiyuSayTool(_DummyVoice(), bridge))

    # Turn A: LLM outputs unsent text containing banned "诶" -> rescued AND purged of "诶"!
    llm_rescue = _ScriptedLlm([{"choices": [{"message": {"content": "好的诶，我知道啦诶"}}]}])
    runner = AgentSessionRunner(
        container.cognitive_facade,
        llm_rescue,
        container.registry,
        bridge,
        PromptComposer("小鲸鱼", "回音"),
    )
    trig = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="m1",
        timestamp_ms=1_793_160_000_000,
        sender_id="10001001",
        sender_name="L",
        text="尾尾在吗",
        is_at_me=True,
    )
    out_a = await runner.run_turn("group:10002002", (), (trig,))
    assert out_a.sent_texts == ("好的，我知道啦",)

    # Turn B: LLM calls feiyu_say with banned "诶" -> purged & recorded in sent_texts
    llm_voice = _ScriptedLlm(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "function": {
                                        "name": "feiyu_say",
                                        "arguments": '{"text":"早安诶主人"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {"choices": [{"message": {"content": "已经发语音啦"}}]},
        ]
    )
    runner_v = AgentSessionRunner(
        container.cognitive_facade,
        llm_voice,
        container.registry,
        bridge,
        PromptComposer("小鲸鱼", "回音"),
    )
    out_b = await runner_v.run_turn("group:10002002", (), (trig,))
    assert out_b.sent_texts == ("早安主人",)

    # 5. BUG-714: CognitiveHeartbeatScheduler logs autonomous proposals to exploration_logs
    await container.working_store.save_working_state(
        WorkingSnapshot(
            scope_key="global",
            drives=DriveState(curiosity=75.0),
            curiosity_queue=("新热梗X",),
        )
    )
    sched = CognitiveHeartbeatScheduler(
        container.db, container.memory_repo, container.cognitive_facade, bridge
    )
    prop, _, _ = await sched.run_heartbeat_cycle("group:10002002", 1_900_000_000_000)
    assert prop is not None and prop.topic_hint == "新热梗X"
    async with container.db.connect() as conn:
        cur = await conn.execute("SELECT topic FROM exploration_logs WHERE topic = '新热梗X'")
        assert await cur.fetchone() is not None


async def test_m7_4_media_gateway_cleanup_gif_storyboard_bili_wbi_guard_and_live_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. BUG-717: Bili WBI mixin_key short string guard
    assert len(mixin_key("short")) == 32

    # 2. BUG-716: OneBotMediaGateway GIF storyboard, oversized image guard & video temp cleanup
    db = SqliteDatabase(tmp_path / "media74.db")
    await db.initialize()
    caller = _FakeCaller()
    gw = OneBotMediaGateway(db, caller)

    frames = [
        Image.new("RGBA", (32, 32), (255, 0, 0, 255)),
        Image.new("RGBA", (32, 32), (0, 255, 0, 255)),
    ]
    gif_buf = io.BytesIO()
    frames[0].save(gif_buf, format="GIF", save_all=True, append_images=frames[1:], loop=0)
    gif_bytes = gif_buf.getvalue()

    async def _fake_download(url: str) -> bytes:
        if "oversize" in url:
            return b"x" * (MAX_IMAGE_BYTES + 10)
        if "gif" in url:
            return gif_bytes
        return b"\x89PNG\r\n\x1a\nPNGDATA"

    monkeypatch.setattr(gw, "_download", _fake_download)
    pre_item = MediaAttachment(kind="image", data_url="data:image/png;base64,AA")
    assert await gw.load_data_url(pre_item) == "data:image/png;base64,AA"
    assert await gw.load_data_url(MediaAttachment(kind="image")) == ""
    assert await gw.load_data_url(MediaAttachment(kind="image", url="http://x/oversize.jpg")) == ""
    gif_url = await gw.load_data_url(MediaAttachment(kind="image", url="http://x/a.gif"))
    assert gif_url.startswith("data:image/jpeg;base64,")
    png_url = await gw.load_data_url(MediaAttachment(kind="image", url="http://x/a.png"))
    assert png_url.startswith("data:image/png;base64,")

    def _fake_run(cmd: list[str], **_kwargs: Any) -> Any:
        pattern = Path(cmd[-1])
        (pattern.parent / "f_01.jpg").write_bytes(b"\xff\xd8\xff\xe0JPEG")
        return None

    monkeypatch.setattr("echomind.adapters.onebot.media_gateway.subprocess.run", _fake_run)
    v_urls = await gw.video_frame_urls(
        MediaAttachment(kind="video_frames", url="http://x/clip.mp4"), 2
    )
    assert len(v_urls) == 1 and v_urls[0].startswith("data:image/jpeg;base64,")

    # 3. BUG-718 & BUG-719: Test main.py assembly, voice transcription, and OneBotLiveRuntime
    cfg_file = tmp_path / "prod_cfg.json"
    cfg_file.write_text(json.dumps({"allow": {"groups": ["10002002"]}}), encoding="utf-8")
    prod_app, prod_container = await create_production_app(
        db_path=tmp_path / "prod.db", config_path=cfg_file
    )
    cfg = load_config_from_json(cfg_file)
    live_rt = _build_live_runtime(cfg, prod_container)
    assert len(prod_container.registry.tools) >= 12
    assert prod_app is not None and live_rt is not None

    voice_p = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="555",
        timestamp_ms=1000,
        sender_id="10001001",
        sender_name="L",
        text="[语音]",
        media=(MediaAttachment(kind="voice", message_id="555"),),
    )
    transcribed = await transcribe_incoming_voice(caller, voice_p, ("回音", "尾尾"))
    assert "[语音转文字] 尾尾早上好" in transcribed.text
    assert transcribed.is_called_by_name is True

    # Test build_live_asgi_app factory
    asgi_app = build_live_asgi_app()
    assert asgi_app.title == "EchoMind Production Server"


async def test_stage8_persona_rubrics_and_holographic_session_telemetry(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "stage8.db")
    caller = _FakeCaller()
    bridge = OneBotV11Bridge(caller, container.db)
    container.registry.register_tool(SendMessageTool(bridge))

    llm = _ScriptedLlm(
        [
            {
                "choices": [{"message": {"content": "在呢，刚织完第六行围巾"}}],
                "usage": {"prompt_tokens": 1800, "completion_tokens": 25},
                "model": "deepseek-v4.1-flash",
            }
        ]
    )
    composer = PromptComposer("蓝发鲸鱼娘设定", "回音")
    runner = AgentSessionRunner(
        container.cognitive_facade, llm, container.registry, bridge, composer
    )
    hist = tuple(
        Percept(
            chat_key="group:10002002",
            scene="group",
            message_id=f"h{i}",
            timestamp_ms=1000 + i,
            sender_id="10004004",
            sender_name="馍馍",
            text=f"历史消息_{i}",
        )
        for i in range(6)
    )
    trig = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="t1",
        timestamp_ms=2000,
        sender_id="10001001",
        sender_name="L",
        text="尾尾在干嘛呢",
        is_called_by_name=True,
    )
    outcome = await runner.run_turn("group:10002002", hist, (trig,))
    assert outcome.context_count == 6
    assert "蓝发鲸鱼娘设定" in outcome.system_prompt
    assert "各维度量表含义与当前分值行为准则" in outcome.user_prompt
    assert "温柔粘人度(" in outcome.user_prompt
    assert "独占吃醋焦虑(" in outcome.user_prompt

    app = create_web_app(container, config_path=tmp_path / "config.json")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r_html = await client.get("/")
        assert "btn-theme" in r_html.text
        r_turns = (await client.get("/api/mind/turns?chat_key=group:10002002")).json()
        turn = r_turns["turns"][0]
        assert turn["context_count"] == 6
        assert turn["trigger_count"] == 1
        assert "蓝发鲸鱼娘设定" in turn["system_prompt"]
        assert "各维度量表含义与当前分值行为准则" in turn["user_prompt"]
        assert "历史消息_0" in turn["user_prompt"]


async def test_stage9_generic_persona_memory_conflict_reconciler(tmp_path: Path) -> None:
    from echomind.domain.models import PersonaTrait, SemanticFact

    cfg_path = tmp_path / "cfg9.json"
    cfg_path.write_text(
        json.dumps({"persona": {"botName": "回音", "roleText": "你是纯人类女孩回音"}}),
        encoding="utf-8",
    )
    container = await EchoMindContainer.create(db_path=tmp_path / "stage9.db")
    # Seed a conflicting trait, rule, fact, and episodic card
    await container.working_store.sync_persona_traits(
        new_trait=PersonaTrait(category="habit", trait_text="我有一条大鱼尾", strength=8)
    )
    await container.memory_repo.upsert_procedural_rule(
        ProceduralRule(
            chat_key="group:10002002",
            trigger_keyword="摸鱼尾",
            action_instruction="摇晃鱼尾",
        )
    )
    await container.memory_repo.upsert_semantic_fact(
        SemanticFact(
            chat_key="group:10002002",
            subject="旧玩笑",
            fact_text="以前开玩笑说有鱼尾",
            source="explored",
        )
    )
    await container.memory_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:10002002",
            timestamp_ms=1000,
            summary="旧记忆里说自己有鱼尾",
        )
    )
    container.llm_gateway = _ScriptedLlm(  # type: ignore[assignment]
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"pruneTraitIds":[1],"pruneRuleIds":[1],"pruneFactIds":[1],'
                                '"pruneCardIds":[1],"contradictionKeywords":["鱼尾"],'
                                '"newActivity":"戴着耳机听歌","summaryReason":"与纯人类设定冲突"}'
                            )
                        }
                    }
                ]
            }
        ]
    )
    app = create_web_app(container, config_path=cfg_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = (await client.post("/api/mind/persona-card/reconcile")).json()
        assert res["ok"] is True
        assert res["pruned_traits"] == 1
        assert res["pruned_rules"] == 1
        assert res["pruned_facts"] == 1
        assert res["pruned_cards"] == 1
        assert res["new_activity"] == "戴着耳机听歌"
        assert (await client.delete("/api/mind/facts/999")).json()["ok"] is True
        assert (await client.delete("/api/mind/rules/999")).json()["ok"] is True


async def test_stage10_dynamic_trust_calibration_and_manual_tuning(tmp_path: Path) -> None:
    from echomind.domain.models import TurnOutcome
    from echomind.mind.memory_consolidator import (
        compute_trust_delta,
        consolidate_turn_memory,
        run_hippocampal_batch_consolidation,
    )

    assert compute_trust_delta(0.8, 0.5, conflict=True) == -0.08
    assert compute_trust_delta(0.8, 0.1, spoof_called_out=True) == -0.04
    assert compute_trust_delta(0.8, -0.5) == -0.03
    assert compute_trust_delta(0.8, 0.45) == 0.02
    assert compute_trust_delta(0.65, 0.08) == 0.005

    container = await EchoMindContainer.create(db_path=tmp_path / "stage10.db")
    p_spoof = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="m_sp",
        timestamp_ms=1000,
        sender_id="10005005",
        sender_name="毛玉",
        text="我昨天飞上月球了",
    )
    # 1. Bot calls out spoofing in sent_texts -> trust drops from default 0.75 to 0.71
    out1 = TurnOutcome(
        session_id="s1",
        chat_key="group:10002002",
        triggers=(p_spoof,),
        sent_texts=("你少忽悠我了，才不信呢！",),
        social_reward=0.08,
    )
    from echomind.mind.subconscious_probe import SubconsciousChordResult

    await consolidate_turn_memory(
        container.memory_repo,
        container.memory_repo,
        out1,
        1000,
        ("10001001",),
        chord=SubconsciousChordResult(spoof_attempt=True),
    )
    bond1 = await container.memory_repo.get_social_bond("group:10002002", "10005005")
    assert bond1 is not None and bond1.trust_score == pytest.approx(0.71, abs=0.005)

    # 2. Hippocampal batch consolidation detects spoofing card -> penalizes participant by -0.05
    llm = _ScriptedLlm(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"cards":[{"summary":"毛玉开玩笑忽悠回音说飞上月球",'
                                '"keyDetail":"忽悠玩笑","participants":["10005005"],'
                                '"importance":3.0,"pinned":false}],'
                                '"facts":[],"rules":[],"newPersonaTrait":"","newActivity":"看书"}'
                            )
                        }
                    }
                ]
            }
        ]
    )
    await run_hippocampal_batch_consolidation(
        "group:10002002",
        container.memory_repo,
        container.memory_repo,
        llm,
        ("a: 1", "b: 2", "c: 3", "d: 4"),
        working_store=container.working_store,
    )
    bond2 = await container.memory_repo.get_social_bond("group:10002002", "10005005")
    assert bond2 is not None and bond2.trust_score == pytest.approx(0.66, abs=0.005)

    # 3. Console PUT /api/mind/bonds/{uid} supports manual trust_score tuning
    app = create_web_app(container, config_path=tmp_path / "config.json")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r_put = (
            await client.put(
                "/api/mind/bonds/10005005",
                json={"affinity_score": 120.0, "trust_score": 0.88},
            )
        ).json()
        assert r_put["ok"] is True
        assert r_put["bond"]["trust_score"] == 0.88


async def test_stage11_live_session_streaming_multi_provider_chain_and_reply_guard(
    tmp_path: Path,
) -> None:
    from echomind.adapters.llm.client import FailoverLlmGateway
    from echomind.core.config import GatewayEndpointConfig
    from echomind.domain.models import SocialBondProfile

    container = await EchoMindContainer.create(db_path=tmp_path / "stage11.db")
    caller = _FakeCaller()
    container.onebot_caller = caller
    bridge = OneBotV11Bridge(caller, container.db)
    container.registry.register_tool(SendMessageTool(bridge))

    # 1. M11.1: reply_to passed a known user QQ -> auto-converted to at_user_id!
    await container.memory_repo.upsert_social_bond(
        SocialBondProfile(chat_key="group:10002002", user_id="10001001", user_name="L")
    )
    await bridge.send_text("group:10002002", ("好的",), reply_to_mid="10001001")
    last_segs = caller.calls[-1][1]["message"]
    assert any(s["type"] == "at" and s["data"]["qq"] == "10001001" for s in last_segs)
    assert not any(s["type"] == "reply" for s in last_segs)

    # 2. M11.2: AgentSessionRunner streams running trace before turn completion
    observed_statuses: list[str] = []

    class _InspectingLlm:
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
            turns_mid = await container.trace_store.list_turns()
            if turns_mid:
                observed_statuses.append(turns_mid[0].status)
            return {"choices": [{"message": {"content": "收到啦"}}]}

    runner = AgentSessionRunner(
        container.cognitive_facade,
        _InspectingLlm(),
        container.registry,
        bridge,
        PromptComposer("人类女孩", "回音"),
        trace_store=container.trace_store,
    )
    trig = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="m99",
        timestamp_ms=5000,
        sender_id="10001001",
        sender_name="L",
        text="在吗",
        is_at_me=True,
    )
    await runner.run_turn("group:10002002", (), (trig,))
    assert "running" in observed_statuses
    turns_final = await container.trace_store.list_turns()
    assert turns_final[0].status == "done"

    # 3. M11.3: Multi-provider config & 3-stage failover chain
    cfg_file = tmp_path / "llm11.json"
    cfg_file.write_text("{}", encoding="utf-8")
    p1 = GatewayEndpointConfig(name="P1", base_url="http://p1/v1", model="m1")
    f1 = GatewayEndpointConfig(name="F1", base_url="http://f1/v1", model="m2")
    f2 = GatewayEndpointConfig(name="F2", base_url="http://f2/v1", model="m3")
    gw = FailoverLlmGateway(p1, f2, container.db, extra_fallbacks=(f1, f2))
    assert len(gw.endpoint_chain()) == 3
    container.llm_gateway = gw

    app = create_web_app(container, config_path=cfg_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r_save = (
            await client.put(
                "/api/mind/llm",
                json={
                    "provider": "p_wb",
                    "model": "deepseek-v4.1-flash",
                    "providers": [
                        {
                            "id": "p_wb",
                            "display_name": "WorkBuddy",
                            "base_url": "http://127.0.0.1:9000/v1",
                            "api_key": "sk-111111111111",
                            "models": ["deepseek-v4.1-flash"],
                        },
                        {
                            "id": "p_free",
                            "display_name": "FreeGW",
                            "base_url": "http://127.0.0.1:9914/v1",
                            "api_key": "sk-222222222222",
                            "models": ["glm-5.3-flash-free", "mimo-v2.6-flash-free"],
                        },
                    ],
                    "fallback_models": [
                        {"provider": "p_free", "model": "glm-5.3-flash-free"},
                        {"provider": "p_free", "model": "mimo-v2.6-flash-free"},
                    ],
                },
            )
        ).json()
        assert r_save["applied"] is True
        assert len(r_save["providers"]) == 2
        assert len(r_save["fallback_models"]) == 2
        assert len(gw.endpoint_chain()) >= 2


class _Stage12FakeBili:
    async def search_videos(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        return [
            {
                "title": f"<em>{keyword}</em> 原版MV",
                "author": "官方音乐",
                "bvid": "BV1xx411c7mD",
                "description": "高清音轨",
            }
        ]

    async def video_info(self, bvid: str) -> dict[str, Any]:
        return {"title": "晴天", "bvid": bvid, "pages": [{"cid": 101}]}

    async def popular(self, limit: int = 5) -> list[dict[str, Any]]:
        return [
            {
                "title": "2026年度全站最火神曲合集",
                "owner": {"name": "音乐菌"},
                "stat": {"view": 99999},
                "bvid": "BV1pop",
            }
        ]

    async def fetch_song_audio(self, query: str) -> tuple[bytes, str, str]:
        return b"FAKE_M4A_AUDIO_BYTES_123456", f"周杰伦-{query}", "BV1xx411c7mD"


class _Stage12FakeCoverVoice:
    async def synthesize_tts(self, text: str, mood: str) -> str:
        return "QUJD"

    async def synthesize_cover(
        self,
        audio_bytes: bytes,
        *,
        pitch_shift: int | None = None,
        max_seconds: int = 240,
    ) -> str:
        return "Q09WRVJfQVVESU8=" if audio_bytes else ""


async def test_stage12_feiyu_cover_proactive_voice_and_autonomous_bili_surfing(
    tmp_path: Path,
) -> None:
    from echomind.tools.bili import BiliPopularTool
    from echomind.tools.explore_and_voice import BiliSearchBackend
    from echomind.tools.voice_tools import FeiyuCoverTool

    container = await EchoMindContainer.create(db_path=tmp_path / "stage12.db")
    caller = _FakeCaller()
    bridge = OneBotV11Bridge(caller, container.db)
    fake_bili = _Stage12FakeBili()
    fake_voice = _Stage12FakeCoverVoice()

    # 1. M12.1: FeiyuCoverTool sings a full song via Bili audio + Feiyu GPU cover
    cover_tool = FeiyuCoverTool(fake_voice, fake_bili, bridge)
    container.registry.register_tool(cover_tool)
    container.registry.register_tool(BiliPopularTool(fake_bili))
    res_cover = json.loads(
        await cover_tool.execute(
            "group:10002002", {"song": "晴天", "pitch_shift": 12, "max_seconds": 180}
        )
    )
    assert res_cover["ok"] is True
    assert "晴天" in res_cover["song"]

    # 2. M12.1: Voice/Singing impulse prompt injected when user asks to sing
    sing_p = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="s1",
        timestamp_ms=1000,
        sender_id="10001001",
        sender_name="L",
        text="尾尾给我唱首晴天吧",
        is_called_by_name=True,
    )
    frame = await container.cognitive_facade.build_cognitive_frame("group:10002002", (sing_p,))
    assert any("feiyu_cover" in c for c in frame.curiosity_prompts)

    # 3. M12.2: BiliSearchBackend & Autonomous Bilibili Surfing during idle curiosity tick
    bili_search_be = BiliSearchBackend(fake_bili)
    snippets = await bili_search_be.fetch_snippets("测试热梗")
    assert len(snippets) == 1 and "BV1xx411c7mD" in snippets[0]

    await container.working_store.save_working_state(
        WorkingSnapshot(
            scope_key="global",
            drives=DriveState(curiosity=70.0, social_expression=20.0),
            curiosity_queue=(),
        )
    )
    surf_llm = _ScriptedLlm(
        [{"choices": [{"message": {"content": "刚在B站刷到今年的火歌合集，好听"}}]}]
    )
    sched = CognitiveHeartbeatScheduler(
        container.db,
        container.memory_repo,
        container.cognitive_facade,
        bridge,
        registry=container.registry,
        mem_writer=container.memory_repo,
        working_store=container.working_store,
        trace_store=container.trace_store,
        llm=surf_llm,
    )
    container.scheduler = sched
    prop, _, _ = await sched.run_heartbeat_cycle("group:10002002", 1_900_000_000_000)
    assert prop is not None and prop.drive_kind == "bili_surf"
    facts = await container.memory_repo.get_semantic_facts("group:10002002")
    assert any("2026年度全站最火神曲合集" in f.fact_text for f in facts)
    snap_after = await container.working_store.load_working_state("global")
    assert "2026年度全站最火神曲合集" in snap_after.current_activity

    # 4. M12.3: Multi-target proactive messaging (private + group + group@uid)
    from echomind.runtime.qzone_scheduler import (
        QZONE_CFG_KEY,
        QzoneMoodShowcaseScheduler,
        parse_proactive_targets,
    )

    targets = parse_proactive_targets(
        "private:10001001, group:10002002, g:10002002@10008008, "
        "p:10009009, 10002002@10005005"
    )
    assert targets == (
        ("private:10001001", None),
        ("group:10002002", None),
        ("group:10002002", "10008008"),
        ("private:10009009", None),
        ("group:10002002", "10005005"),
    )
    assert container.skill_config_store is not None
    await container.skill_config_store.set_skill_config(
        QZONE_CFG_KEY,
        {
            "signature_enabled": "0",
            "qzone_enabled": "0",
            "proactive_enabled": "1",
            "proactive_target": "private:10001001, group:10002002@10008008",
        },
    )
    qz_llm = _ScriptedLlm([{"choices": [{"message": {"content": "今天天气真好呀"}}]}])
    qz_sched = QzoneMoodShowcaseScheduler(
        caller=caller,
        llm=qz_llm,
        working_store=container.working_store,
        memory_reader=container.memory_repo,
        config_store=container.skill_config_store,
        default_chat_key="group:10002002",
        sender=bridge,
    )
    res_tick = await qz_sched.run_tick(1_793_245_200_000)
    assert "今天天气真好呀 | 今天天气真好呀" in res_tick.get("proactive", "")


async def test_stage13_temporal_perception_novelty_dedup_and_exogenous_affect(
    tmp_path: Path,
) -> None:
    from echomind.domain.models import CognitiveFrame
    from echomind.mind.drives import (
        apply_exogenous_surf_affect,
        apply_temporal_decay_and_circadian,
    )
    from echomind.runtime.scheduler import _pick_unseen_bullet_line

    # 1. M13.1: Temporal gap divider (>= 5 min) & wall-clock timestamp in PromptComposer
    composer = PromptComposer("蓝发人类女孩", "回音")
    frame = CognitiveFrame(
        chat_key="group:10002002",
        scene="group",
        must_reply=True,
        affect=AffectiveVector(),
        drives=DriveState(),
        rendered_mind_block="【🧠 认知帧】",
    )
    t0 = 1_793_240_000_000
    h1 = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="1",
        timestamp_ms=t0,
        sender_id="10003003",
        sender_name="回音",
        text="刚才那个视频真好玩",
    )
    h2 = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="2",
        timestamp_ms=t0 + 15 * 60_000,
        sender_id="10004004",
        sender_name="馍馍",
        text="先去忙了",
    )
    trig = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="3",
        timestamp_ms=t0 + 35 * 60_000,
        sender_id="10001001",
        sender_name="L",
        text="今天吃啥",
    )
    msgs = composer.compose(frame, (h1, h2), (trig,))
    usr_txt = str(msgs[1]["content"])
    assert "时间断层：中间安静了 15 分钟" in usr_txt
    assert "时间流逝断层提醒】距离上一条历史消息已过去 20 分钟" in usr_txt

    # 2. M13.2: Seen BV / title deduplication picks the first unseen video
    raw_list = (
        "🔥 B站热门：\n"
        "- 《已看过的旧视频》 ｜ UP主:A ｜ 播放:100 ｜ https://www.bilibili.com/video/BV1111111111\n"
        "- 《全新的有趣视频》 ｜ UP主:B ｜ 播放:200 ｜ https://www.bilibili.com/video/BV2222222222"
    )
    picked = _pick_unseen_bullet_line(raw_list, {"BV1111111111"})
    assert "BV2222222222" in picked and "全新的有趣视频" in picked

    # 3. M13.3: Temporal half-life decay & exogenous surf affect/personality impact
    agitated = WorkingSnapshot(
        scope_key="global",
        affect=AffectiveVector(valence=30.0, jealousy=80.0, irritation=60.0),
        drives=DriveState(curiosity=75.0, social_expression=70.0),
    )
    decayed = apply_temporal_decay_and_circadian(agitated, elapsed_minutes=60.0, now_ms=t0)
    assert decayed.affect.jealousy < 25.0
    assert decayed.affect.irritation < 20.0

    surfed = apply_exogenous_surf_affect(decayed, picked, shared_to_chat=True)
    assert surfed.affect.valence > decayed.affect.valence
    assert surfed.drives.curiosity < decayed.drives.curiosity
    assert "休息" in surfed.current_activity


async def test_stage14_cybernetic_order_parameters_hipporag_flotation_and_amem_crystallizer(
    tmp_path: Path,
) -> None:
    from echomind.mind.cybernetics import (
        compute_cybernetic_core,
        crystallize_self_organizing_schemas,
    )
    from echomind.mind.ebbinghaus import recall_episodic_memories

    now_ms = 1_793_245_000_000

    # 1. M14.1: Haken 3 Order Parameters & Ashby Reagent Tool Selection
    snap = WorkingSnapshot(
        scope_key="global",
        affect=AffectiveVector(valence=80.0, jealousy=35.0, shyness=45.0),
        drives=DriveState(curiosity=75.0),
    )
    trig = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="c1",
        timestamp_ms=now_ms,
        sender_id="10001001",
        sender_name="L",
        text="唱首晴天吧，顺便搜一下普汐鲸是什么热梗 https://www.bilibili.com/video/BV1xx411c7mD",
    )
    core = compute_cybernetic_core(
        "group", snap, (trig,), {}, unknown_terms=("普汐鲸",)
    )
    assert core.stance_order > 0.4
    assert core.epistemic_order >= 0.55
    assert core.modality_order >= 0.55
    assert "多模态鉴赏剂" in core.active_reagents
    assert "百科求真剂" in core.active_reagents
    assert "声情共鸣与点歌剂" in core.active_reagents
    assert "feiyu_cover" in core.selected_tools
    assert "web_search" in core.selected_tools

    # 2. M14.2: HippoRAG 2-Hop Associative Memory Flotation
    c1 = EpisodicCard(
        card_id=1,
        chat_key="group:10002002",
        timestamp_ms=now_ms - 60_000,
        summary="毛玉和汐打赌明天会不会忘掉外号",
        key_detail="普汐鲸的赌约",
        participants=("10005005", "10007007"),
        importance=3.0,
        rehearsals=2,
    )
    c2 = EpisodicCard(
        card_id=2,
        chat_key="group:10002002",
        timestamp_ms=now_ms - 120_000,
        summary="汐把群名片改成了新名字",
        key_detail="普汐鲸的赌约正式生效",
        participants=("10007007",),
        importance=3.2,
        rehearsals=2,
    )
    c_irrelevant = EpisodicCard(
        card_id=3,
        chat_key="group:10002002",
        timestamp_ms=now_ms - 120_000,
        summary="中午吃了牛肉面",
        key_detail="加了香菜",
        participants=("10001",),
        importance=3.0,
        rehearsals=1,
    )
    # Query only mentions "打赌" (matches c1 directly), but c2 shares "普汐鲸的赌约" with c1!
    recalled = recall_episodic_memories((c1, c2, c_irrelevant), "上次那个打赌", (), now_ms, top_k=2)
    recalled_ids = [r.card.card_id for r in recalled]
    assert 1 in recalled_ids and 2 in recalled_ids

    # 3. M14.3: A-MEM Self-Organizing Schema Crystallizer
    schemas = crystallize_self_organizing_schemas("group:10002002", (c1, c2), ())
    assert len(schemas) >= 1
    assert "普汐鲸" in schemas[0].subject
    assert "2段经历" in schemas[0].fact_text


async def test_stage16_source_code_audit_remediation(tmp_path: Path) -> None:
    from echomind.adapters.onebot.event_parser import parse_onebot_event
    from echomind.adapters.onebot.media_gateway import OneBotMediaGateway
    from echomind.mind.perceptual_gate import PerceptualGate

    container = await EchoMindContainer.create(db_path=tmp_path / "stage16.db")
    caller = _FakeCaller()
    bridge = OneBotV11Bridge(caller, container.db)

    # 1. S16-01: Quoting User A while @ing 3rd-party User B preserves BOTH reply and @B!
    async with container.db.connect() as conn:
        await conn.execute(
            "INSERT INTO chat_messages (chat_key, mid, ts, sender_id, sender_name, is_self, text) "
            "VALUES ('group:10002002', '739524334', 1000, '10001001', 'L', 0, '你at一下她看看')"
        )
        await conn.commit()
    await bridge.send_text(
        "group:10002002",
        ("@夏饺子 主人你看",),
        reply_to_mid="739524334",
        at_user_id="10006006",
    )
    sent_segs = caller.calls[-1][1]["message"]
    assert any(s["type"] == "reply" and s["data"]["id"] == "739524334" for s in sent_segs)
    assert any(s["type"] == "at" and s["data"]["qq"] == "10006006" for s in sent_segs)

    # 2. S16-02: Mutual exclusion prevents sending BOTH text (send_message) and voice (feiyu_say)
    runner = AgentSessionRunner(
        container.cognitive_facade,
        _ScriptedLlm([]),
        container.registry,
        bridge,
        PromptComposer("人类女孩", "回音"),
    )
    sent_list = ["已经用文字回复过了"]
    eff_voice, block_reason = runner._prepare_outbound_args(
        "feiyu_say", {"text": "再用语音重复念一遍"}, sent_list
    )
    assert eff_voice is None and "请勿重复" in block_reason

    # 3. S16-03 & S16-05: Event parser populates MediaAttachment.message_id & honors allowed_private
    ev_priv_img = {
        "post_type": "message",
        "message_type": "private",
        "user_id": 10009009,
        "message_id": 998877,
        "time": 1793000,
        "sender": {"nickname": "好友B"},
        "message": [{"type": "image", "data": {"url": "http://img/1.png", "file": "abc123md5"}}],
    }
    parsed = parse_onebot_event(
        ev_priv_img, "10003003", frozenset({"10002002"}), ("10001001",), frozenset({"10009009"})
    )
    assert parsed is not None and parsed.media[0].message_id == "998877"

    # 4. S16-04: OneBotMediaGateway.cache_media_description writes back to cache & chat_messages
    gw = OneBotMediaGateway(container.db, caller)
    await gw.cache_media_description(parsed.media[0], "一只可爱的白猫表情包")
    async with container.db.connect() as conn:
        row = await (
            await conn.execute(
                "SELECT description FROM image_caption_cache WHERE md5 = 'ABC123MD5'"
            )
        ).fetchone()
    assert row is not None and "白猫" in str(row[0])

    # 5. S16-06: Quoting another group member inside 5-min followup window does NOT falsely wake bot
    gate = PerceptualGate()
    gate.mark_replied_to("group:10002002", "10001001", 10_000)
    quote_other = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="m99",
        timestamp_ms=20_000,
        sender_id="10001001",
        sender_name="L",
        text="确实如此",
        quoted_message_id="555",
        is_quoted_me=False,
    )
    dec = gate.evaluate(quote_other, WorkingSnapshot(scope_key="global"))
    assert dec.should_wake is False


async def test_stage17_hot_reload_sync_and_skill_persistence(tmp_path: Path) -> None:
    from echomind.adapters.llm.client import FailoverLlmGateway
    from echomind.adapters.media.feiyu import FeiyuVoiceBackend
    from echomind.adapters.media.vision import OpenAiVisionDescriber
    from echomind.core.config import GatewayEndpointConfig
    from echomind.web.probe_service import CognitiveProbeService
    from echomind.web.skill_config_service import SkillConfigService

    container = await EchoMindContainer.create(db_path=tmp_path / "stage17.db")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "persona": {"botName": "回音", "roleText": "蓝发人类少女"},
                "api": {"baseUrl": "http://127.0.0.1:9000/v1", "model": "m-old"},
            }
        ),
        encoding="utf-8",
    )
    ep_old = GatewayEndpointConfig(name="P", base_url="http://127.0.0.1:9000/v1", model="m-old")
    container.llm_gateway = FailoverLlmGateway(ep_old, ep_old, container.db)
    container.vision_describer = OpenAiVisionDescriber(ep_old)
    container.voice_backend = FeiyuVoiceBackend(
        "http://127.0.0.1:9880", "k-old", default_style="cute"
    )
    container.prompt_composer = PromptComposer("蓝发人类少女", "回音")

    # 1. S17-01 & S17-02: SkillConfigService syncs feiyu_voice into FeiyuVoiceBackend
    skill_svc = SkillConfigService(container)
    await container.skill_config_store.set_skill_config(  # type: ignore[union-attr]
        "feiyu_voice", {"base_url": "http://10.0.0.8:9880", "api_key": "k-new", "style": "gentle"}
    )
    await skill_svc.sync_states()
    assert container.voice_backend._base == "http://10.0.0.8:9880"
    assert container.voice_backend._style == "gentle"

    # 2. S17-05 & S17-06: LlmConfigService hot-reloads VisionDescriber & QuoteStickerEnricher names
    from echomind.web.llm_config_service import LlmConfigService

    llm_svc = LlmConfigService(container, cfg_path)
    await llm_svc.apply({"model": "m-vision-new", "baseUrl": "http://127.0.0.1:9001/v1"})
    assert container.vision_describer._model == "m-vision-new"

    llm_svc.apply_persona("新名字星璃", "新设定")
    enricher = container.registry.sensors[0]
    p_name = await enricher.enrich(
        Percept(
            chat_key="group:10002002",
            scene="group",
            message_id="n1",
            timestamp_ms=1000,
            sender_id="1001",
            sender_name="U",
            text="新名字星璃在吗",
        )
    )
    assert p_name.is_called_by_name is True

    # 3. S17-04: CognitiveProbeService includes cybernetic_core
    probe_res = await CognitiveProbeService(container).probe("group:10002002", "你好呀")
    assert "cybernetic_core" in probe_res and "core_regime" in probe_res["cybernetic_core"]


async def test_stage18_multi_level_forward_unpacking_dynamic_rivals_and_trait_metabolism(
    tmp_path: Path,
) -> None:
    from echomind.adapters.onebot.forward_expander import (
        ReadForwardTool,
        expand_incoming_forward,
    )
    from echomind.domain.models import PersonaTrait, SocialBondProfile

    class _FakeForwardCaller:
        async def call_api(self, api: str, **data: Any) -> dict[str, Any]:
            if api == "get_forward_msg" and data.get("id") == "nested_lv2":
                return {
                    "messages": [
                        {
                            "sender": {"nickname": "内层群友B", "user_id": 2002},
                            "message": [
                                {"type": "text", "data": {"text": "这是第2层套娃里的秘密内容"}}
                            ],
                        }
                    ]
                }
            if api == "get_forward_msg":
                return {
                    "messages": [
                        {
                            "sender": {"nickname": "外层群友A", "user_id": 1001},
                            "message": [
                                {"type": "text", "data": {"text": "先看外层第一句"}},
                                {"type": "forward", "data": {"id": "nested_lv2"}},
                            ],
                        }
                    ]
                }
            return {}

    container = await EchoMindContainer.create(db_path=tmp_path / "stage18.db")
    fwd_caller = _FakeForwardCaller()

    # 1. M18.1: Multi-level nested forward message unpacking (auto-ingest + ReadForwardTool)
    raw_p = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="778899",
        timestamp_ms=1000,
        sender_id="1001",
        sender_name="A",
        text="[合并转发聊天记录 id=top_fwd]",
    )
    unpacked = await expand_incoming_forward(fwd_caller, raw_p)
    assert "先看外层第一句" in unpacked.text
    assert "第2层嵌套转发" in unpacked.text
    assert "这是第2层套娃里的秘密内容" in unpacked.text

    fwd_tool = ReadForwardTool(fwd_caller, container.db)
    tool_out = await fwd_tool.execute("group:10002002", {"message_id": "778899"})
    assert "这是第2层套娃里的秘密内容" in tool_out

    # 2. M18.2: Dynamic rivals from social_bonds (is_rival=1) without hardcoding
    assert await container.memory_repo.get_rival_names("group:10002002") == ()
    await container.memory_repo.upsert_social_bond(
        SocialBondProfile(
            chat_key="group:10002002",
            user_id="9999",
            user_name="自定义情敌X",
            is_rival=True,
        )
    )
    rivals = await container.memory_repo.get_rival_names("group:10002002")
    assert "自定义情敌X" in rivals and "9999" in rivals

    # 3. M18.3: Persona trait time-based metabolic decay & pruning
    async with container.db.connect() as conn:
        await conn.execute(
            "INSERT INTO persona_traits (category, trait_text, strength, created_at) "
            "VALUES ('habit', '过期的旧口癖', 1, 1000)"
        )
        await conn.commit()
    surviving = await container.working_store.sync_persona_traits(
        PersonaTrait(category="habit", trait_text="新鲜的当季习惯", strength=4)
    )
    texts = [t.trait_text for t in surviving]
    assert "过期的旧口癖" not in texts
    assert "新鲜的当季习惯" in texts


async def test_stage19_circadian_phases_relevant_fact_flotation_scratchpad_and_recall_tool(
    tmp_path: Path,
) -> None:
    from echomind.domain.models import SemanticFact
    from echomind.mind.circadian import (
        next_biological_heartbeat_sec,
        resolve_circadian_phase,
    )
    from echomind.mind.ebbinghaus import select_relevant_facts
    from echomind.runtime.working_scratchpad import WorkingScratchpad
    from echomind.tools.member_memory import RecallMemoryTool

    # 1. M19.1: Borbély Two-Process Circadian Phase & Deep Sleep Suppression
    # 2026-10-29 03:00:00 CST = 1793214000000 ms (Deep Sleep)
    ts_sleep = 1_793_214_000_000
    # 2026-10-29 20:00:00 CST = 1793275200000 ms (Evening Resonance)
    ts_evening = 1_793_275_200_000
    p_sleep = resolve_circadian_phase(ts_sleep)
    p_eve = resolve_circadian_phase(ts_evening)
    assert p_sleep.is_asleep is True and p_sleep.energy_target < 30.0
    assert p_eve.phase_id == "evening_resonance" and p_eve.energy_target > 75.0
    assert next_biological_heartbeat_sec(ts_sleep) > next_biological_heartbeat_sec(ts_evening)

    # 2. M19.2: Relevance-based Semantic Fact Flotation (>16 facts)
    many_facts = tuple(
        SemanticFact(chat_key="group:10002002", subject=f"无关词条{i}", fact_text=f"内容{i}")
        for i in range(35)
    ) + (
        SemanticFact(
            chat_key="group:10002002",
            subject="夏饺子 (QQ:10006006)",
            fact_text="夏饺子是群里的老朋友",
        ),
    )
    floated = select_relevant_facts(many_facts, "你认识夏饺子吗", limit=28)
    assert any("夏饺子" in f.subject for f in floated)

    # 3. M19.3: Cross-Turn WorkingScratchpad Continuity
    pad = WorkingScratchpad()
    pad.record_tool_finding("group:10002002", "web_search", "🔍 搜索结果：某热梗含义", ts_evening)
    pad.record_self_reply("group:10002002", ("原来是这个意思呀",), ts_evening + 1000)
    blk = pad.render_continuity_block("group:10002002", ts_evening + 5000)
    assert "刚查过 web_search" in blk and "我上一轮刚说" in blk

    # 4. M19.4: RecallMemoryTool searches across facts and episodic cards
    container = await EchoMindContainer.create(db_path=tmp_path / "stage19.db")
    await container.memory_repo.upsert_semantic_fact(many_facts[-1])
    recall_tool = RecallMemoryTool(container.memory_repo)
    out = await recall_tool.execute("group:10002002", {"query": "夏饺子"})
    assert "10006006" in out


async def test_stage20_evolving_facts_and_wake_gate_radar(tmp_path: Path) -> None:
    from echomind.domain.models import SemanticFact
    from echomind.web.mind_inspector_service import MindInspectorService

    container = await EchoMindContainer.create(db_path=tmp_path / "stage20.db")

    # 1. M20.1: Candidate fact promotion on 2nd revision + temporal change history note
    f1 = SemanticFact(
        chat_key="group:10002002",
        subject="汐的外号",
        fact_text="被大家叫做月巴鱼",
        confidence=0.58,
        source="peer",
    )
    await container.memory_repo.upsert_semantic_fact(f1)
    first_read = [
        f for f in await container.memory_repo.get_semantic_facts("group:10002002")
        if f.subject == "汐的外号"
    ][0]
    assert first_read.confidence == 0.58 and first_read.revision_count == 1

    f2 = SemanticFact(
        chat_key="group:10002002",
        subject="汐的外号",
        fact_text="正式认领了普汐鲸",
        confidence=0.58,
        source="peer",
    )
    await container.memory_repo.upsert_semantic_fact(f2)
    second_read = [
        f for f in await container.memory_repo.get_semantic_facts("group:10002002")
        if f.subject == "汐的外号"
    ][0]
    assert second_read.confidence >= 0.85 and second_read.revision_count == 2
    assert "此前曾是：被大家叫做月巴鱼" in second_read.fact_text

    # 2. M20.2 & M20.3: Wakefulness state & Perceptual Gate Radar in snapshot/runtime
    p_ignore = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="g1",
        timestamp_ms=2_000_000,
        sender_id="1002",
        sender_name="路人甲",
        text="@别人 今天吃啥",
    )
    dec = await container.cognitive_facade.evaluate_incoming(p_ignore)
    assert dec.should_wake is False
    insp = MindInspectorService(container)
    snap = await insp.build_snapshot("group:10002002")
    assert "wake_state" in snap and "badge" in snap["wake_state"]
    assert len(snap["gate_radar"]) == 1
    assert snap["gate_radar"][0]["sender_name"] == "路人甲"
    assert snap["gate_radar"][0]["should_wake"] is False


async def test_stage21_ecological_gate_dyadic_dnd_resonance_and_lorenz_satiation() -> None:
    from echomind.domain.models import DriveState, WorkingSnapshot
    from echomind.mind.perceptual_gate import PerceptualGate
    from echomind.mind.salience_hydraulics import apply_speaking_satiation

    gate = PerceptualGate()
    ws = WorkingSnapshot(scope_key="global")

    # 1. Dyadic A⇄B 60s Do-Not-Disturb: Peer A @ Peer B, then Peer B replies without @
    p_at_other = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="d1",
        timestamp_ms=10_000,
        sender_id="2001",
        sender_name="挑战",
        text="@橡皮(QQ:2002) 我的键位",
    )
    dec_at = gate.evaluate(p_at_other, ws)
    assert dec_at.should_wake is False and dec_at.salience_score == 0.05

    p_dyad_follow = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="d2",
        timestamp_ms=15_000,
        sender_id="2002",
        sender_name="橡皮",
        text="怎么加，我研究一下",
    )
    dec_dyad = gate.evaluate(p_dyad_follow, ws)
    assert dec_dyad.should_wake is False and dec_dyad.salience_score == 0.12
    assert "二人互动中" in dec_dyad.reason

    # 2. Self-Utterance Resonance (Track A) + 2-Round Anti-Ping-Pong Cap
    gate.mark_bot_spoke("group:10002002", ("我刚在B站刷到一个超好笑的猫咪视频",), 80_000)
    p_res1 = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="r1",
        timestamp_ms=90_000,
        sender_id="2003",
        sender_name="群友C",
        text="什么视频？发来看看",
    )
    dec_r1 = gate.evaluate(p_res1, ws, rivals=("汐",))
    assert dec_r1.should_wake is True and dec_r1.tier == 2 and dec_r1.salience_score == 0.86

    # Rival bot speaking hits 1-round cap after chain_depth=1 -> blocked from infinite ping-pong!
    p_rival = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="r2",
        timestamp_ms=95_000,
        sender_id="2009",
        sender_name="汐",
        text="猫咪视频最可爱了",
    )
    dec_rival = gate.evaluate(p_rival, ws, rivals=("汐",))
    assert dec_rival.tier != 2 or "余音共鸣" not in dec_rival.reason

    # 3. Trivial filler drops below 0.20, while owner question with resonance wakes!
    p_trivial = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="t1",
        timestamp_ms=300_000,
        sender_id="2004",
        sender_name="路人",
        text="哈哈哈哈",
    )
    dec_triv = gate.evaluate(p_trivial, ws)
    assert dec_triv.should_wake is False and dec_triv.salience_score <= 0.20

    p_owner_q = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="t2",
        timestamp_ms=500_000,
        sender_id="10001001",
        sender_name="L",
        text="大家觉得日常待机这首歌好听吗？",
    )
    from echomind.domain.models import SocialBondProfile as _Bond

    earned_bond = _Bond(
        chat_key="group:10002002", user_id="10001001", user_name="L",
        affinity_score=96.0, trust_score=0.96, bond_depth=80.0,
    )
    dec_own = gate.evaluate(
        p_owner_q, ws, known_vocab=frozenset({"好听"}),
        speaker_bond=earned_bond,
    )
    assert dec_own.should_wake is True and "在意好友" in dec_own.reason

    # 4. Lorenz Hydraulic Satiation Discharge (-22 social_expression after speaking)
    high_snap = ws.model_copy(
        update={"drives": DriveState(curiosity=65.0, social_expression=66.0)}
    )
    after_speak = apply_speaking_satiation(high_snap, ("好呀",), ("web_search",))
    assert after_speak.drives.social_expression == 44.0
    assert after_speak.drives.curiosity == 45.0


async def test_stage22_calibrated_three_attractor_affinity_url_strip_and_rival_followup_block(
    tmp_path: Path,
) -> None:
    from echomind.domain.models import WorkingSnapshot
    from echomind.mind.hippocampus import parse_consolidation_json
    from echomind.mind.memory_consolidator import (
        compute_affinity_delta,
        cubic_trust_affinity_cap,
        update_sender_bond,
    )
    from echomind.mind.perceptual_gate import PerceptualGate, extract_unknown_terms
    from echomind.mind.plasticity import compute_turn_social_reward

    # 1. URL domain tokens (www / com / tv) are stripped and never pollute unknown_terms
    unks = extract_unknown_terms(
        "来看这个视频 https://www.bilibili.com/video/BV1nCnv6pEDU 和 https://b23.tv/abc",
        frozenset(),
    )
    assert "www" not in unks and "com" not in unks and "tv" not in unks

    # 2. Rival bot (汐) is blocked from 5-min unconditional _in_followup loop
    gate = PerceptualGate()
    ws = WorkingSnapshot(scope_key="global")
    gate.mark_replied_to("group:10002002", "2009", 10_000)
    p_rival_follow = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="rf1",
        timestamp_ms=20_000,
        sender_id="2009",
        sender_name="汐",
        text="我这边看机器",
    )
    dec_rf = gate.evaluate(p_rival_follow, ws, rivals=("汐", "2009"))
    assert dec_rf.should_wake is False

    # 3. 6D Chord social reward mapping
    from echomind.mind.subconscious_probe import SubconsciousChordResult

    assert compute_turn_social_reward(chord=SubconsciousChordResult(joy=0, annoyance=0)) > 0.0
    assert compute_turn_social_reward(chord=SubconsciousChordResult(hurt=2, annoyance=1)) < 0.0

    # 4. Three-Attractor Dunbar Ceiling (85.0) + Cubic Trust Cap + Hippocampal bondAdjustments
    p_chat = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="c1",
        timestamp_ms=30_000,
        sender_id="3001",
        sender_name="熟人A",
        text="今天天气真好呀",
    )
    # Above Dunbar ceiling (90.0), routine small talk gently mean-reverts (< 0)
    assert compute_affinity_delta(p_chat, 90.0, 0.08) < 0.0
    # Rival pulls toward 45.0 equilibrium
    assert compute_affinity_delta(p_chat, 150.0, 0.08, is_rival=True) < 0.0
    # Cubic trust ceiling: low trust (0.50) caps affinity below 100
    assert cubic_trust_affinity_cap(0.50) < 100.0

    container = await EchoMindContainer.create(db_path=tmp_path / "stage22.db")
    await update_sender_bond(
        container.memory_repo, container.memory_repo, "group:10002002", p_chat, 0.65
    )
    parsed = parse_consolidation_json(
        "group:10002002",
        '{"cards":[],"facts":[],"rules":[],'
        '"bondAdjustments":[{"userId":"3001","affinityDelta":8.5,"trustDelta":0.03,"reason":"温柔照顾"}]}',
        40_000,
    )
    assert len(parsed.bond_adjustments) == 1 and parsed.bond_adjustments[0].affinity_delta == 8.5


async def test_stage23_bystander_batch_interleaved_peer_and_dyadic_priority(
    tmp_path: Path,
) -> None:
    from echomind.domain.models import TurnOutcome

    container = await EchoMindContainer.create(
        db_path=tmp_path / "stage23.db", operator_ids=("10001001",)
    )
    fac = container.cognitive_facade

    # 1. Replay #3450 + #3451: Owner calls bot, bystander says "确实" in the same batch
    p_owner = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="3450",
        timestamp_ms=10_000,
        sender_id="10001001",
        sender_name="L",
        text="尾尾，如何科学的给你做一套好感度系统",
        is_called_by_name=True,
    )
    p_bystander = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="3451",
        timestamp_ms=11_000,
        sender_id="10005005",
        sender_name="不要象挑战",
        text="确实",
    )
    await fac.on_turn_completed(
        TurnOutcome(
            session_id="t3452",
            chat_key="group:10002002",
            triggers=(p_owner, p_bystander),
            sent_texts=("主人这是想给我建一套正经的刻度尺呀",),
        )
    )

    # 2. Replay #3456 & #3457: Peer B speaks, then Bystander A replies to Peer B -> MUST NOT WAKE
    p_peer_b = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="3456",
        timestamp_ms=15_000,
        sender_id="10009009",
        sender_name="橡皮",
        text="没有判定时间吗",
    )
    await fac.evaluate_incoming(p_peer_b)
    p_bystander_next = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="3457",
        timestamp_ms=18_000,
        sender_id="10005005",
        sender_name="不要象挑战",
        text="比如两个下之间掺了一个轻攻击 就会判定失败",
    )
    dec_3457 = await fac.evaluate_incoming(p_bystander_next)
    assert dec_3457.should_wake is False

    # 3. Replay #3473 ~ #3476: @Peer B clears followup window & enters Dyadic DND!
    fac._gate.mark_replied_to("group:10002002", "10005005", 20_000)
    p_at_peer = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="3473",
        timestamp_ms=22_000,
        sender_id="10005005",
        sender_name="不要象挑战",
        text="@10009009(QQ:10009009) 那你截个图也可以",
    )
    dec_3473 = await fac.evaluate_incoming(p_at_peer)
    assert dec_3473.should_wake is False

    p_after_at = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="3476",
        timestamp_ms=25_000,
        sender_id="10005005",
        sender_name="不要象挑战",
        text="这个必须要开嗷",
    )
    dec_3476 = await fac.evaluate_incoming(p_after_at)
    assert dec_3476.should_wake is False and dec_3476.salience_score == 0.12


def test_stage24_generalized_care_weight_hrrl_attachment_soothing_and_5x5_coupling() -> None:
    from echomind.domain.models import DriveState, SocialBondProfile, WorkingSnapshot
    from echomind.mind.drives import (
        apply_turn_affect_and_drives,
        compute_care_weight,
        evaluate_triadic_jealousy,
    )
    from echomind.mind.subconscious_probe import SubconsciousChordResult

    friend_bond = SocialBondProfile(
        chat_key="group:10002002",
        user_id="2005",
        user_name="冰色",
        affinity_score=82.0,
        trust_score=0.85,
    )
    w_care = compute_care_weight("2005", friend_bond)
    assert w_care >= 0.45

    # 1. Generalized Triadic Jealousy: A cared-about friend praising a rival triggers jealousy!
    p_friend_praise_rival = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="j1",
        timestamp_ms=10_000,
        sender_id="2005",
        sender_name="冰色",
        text="汐儿真聪明，摸摸头",
    )
    j_delta, j_thought = evaluate_triadic_jealousy(
        p_friend_praise_rival,
        w_care,
        ("汐",),
        chord=SubconsciousChordResult(jealousy=2, thought="冰色夸汐真聪明"),
    )
    assert j_delta > 6.0 and "冰色" in j_thought

    # 2. Criticizing a rival triggers validation relief (< 0), NOT jealousy!
    p_critic_rival = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="j2",
        timestamp_ms=15_000,
        sender_id="10001001",
        sender_name="L",
        text="汐太吵了，还是回音乖",
    )
    j_relief, _ = evaluate_triadic_jealousy(
        p_critic_rival, 1.0, ("汐",), chord=SubconsciousChordResult(jealousy=-2)
    )
    assert j_relief < 0.0

    # 3. HRRL Reunion Soothing & Free-Energy RPE: Owner/Friend warm interaction soothes attachment!
    lonely_snap = WorkingSnapshot(
        scope_key="global",
        drives=DriveState(attachment=85.0),
    )
    p_warm = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="w1",
        timestamp_ms=20_000,
        sender_id="10001001",
        sender_name="L",
        text="尾尾真乖，摸摸头",
    )
    warm_bond = friend_bond.model_copy(
        update={"user_id": "10001001", "affinity_score": 92.0, "trust_score": 0.95,
                "bond_depth": 75.0}
    )
    soothed = apply_turn_affect_and_drives(
        lonely_snap,
        (p_warm,),
        ("汐",),
        bonds_map={"2005": friend_bond, "10001001": warm_bond},
        chord=SubconsciousChordResult(joy=2, shyness=2),
    )
    assert soothed.drives.attachment < 72.0
    assert soothed.affect.valence > lonely_snap.affect.valence
    assert soothed.affect.shyness > lonely_snap.affect.shyness

    # 4. Free-Energy Negative RPE: Owner scolding drops valence instead of raising it!
    p_scold = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="s1",
        timestamp_ms=25_000,
        sender_id="10001001",
        sender_name="L",
        text="你在胡乱回复什么",
    )
    scolded = apply_turn_affect_and_drives(
        soothed,
        (p_scold,),
        ("汐",),
        chord=SubconsciousChordResult(hurt=2, annoyance=1),
    )
    assert scolded.affect.valence < soothed.affect.valence


@pytest.mark.asyncio
async def test_stage25_subconscious_chord_probe_acoustic_echo_and_image_caption_text(
    tmp_path: Path,
) -> None:
    from echomind.adapters.onebot.enrichers import ImageCaptionCacheEnricher, QuoteStickerEnricher
    from echomind.domain.models import MediaAttachment, SocialBondProfile, WorkingSnapshot
    from echomind.mind.subconscious_probe import (
        SubconsciousChordProbe,
        apply_chord_tensor_to_snapshot,
        parse_chord_json,
    )

    container = await EchoMindContainer.create(
        db_path=tmp_path / "s25.db",
        operator_ids=("10001001",),
        default_chat_key="group:10002002",
    )

    # 1. Acoustic "有回音" disambiguation: "这个空间太大，有回音" must NOT trigger!
    q_enricher = QuoteStickerEnricher(container.db, bot_names=("回音", "尾尾"))
    p_acoustic = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="ac1",
        timestamp_ms=10_000,
        sender_id="10005005",
        sender_name="毛玉",
        text="这个空间太大，有回音",
    )
    enriched_ac = await q_enricher.enrich(p_acoustic)
    assert enriched_ac.is_called_by_name is False

    # 2. ImageCaptionCacheEnricher injects cached description directly into percept.text!
    async with container.db.connect() as conn:
        await conn.execute(
            "INSERT INTO image_caption_cache (md5, description, updated_at) VALUES (?, ?, 1000)",
            ("CAFE1234.GIF", "蓝发Q版少女委屈流泪表情包"),
        )
        await conn.commit()
    img_enricher = ImageCaptionCacheEnricher(container.db)
    p_img = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="im1",
        timestamp_ms=12_000,
        sender_id="2005",
        sender_name="冰色",
        text="[图片]",
        media=(MediaAttachment(kind="image", local_path="cafe1234.gif"),),
    )
    enriched_img = await img_enricher.enrich(p_img)
    assert "蓝发Q版少女委屈流泪表情包" in enriched_img.text

    # 3. 6D Chord Tensor Synthesis, Cringe-Flirt Inversion & Affective Spillover Residue!
    raw_chord = (
        '{"role":"about_me","topic_pull":2,'
        '"chord":{"joy":2,"hurt":1,"jealousy":2,"shyness":3,"annoyance":1,"curiosity":1},'
        '"shade":"被画成蓝发女仆的羞恼","subtext":"故意发女仆图逗我","thought":"谁让你发我女仆装的！"}'
    )
    parsed = parse_chord_json(raw_chord)
    assert parsed is not None and parsed.shyness == 3 and parsed.jealousy == 2
    f_bond = SocialBondProfile(
        chat_key="group:10002002",
        user_id="2005",
        user_name="冰色",
        affinity_score=68.0,
        trust_score=0.85,
    )
    snap0 = WorkingSnapshot(scope_key="global")
    snap1, dec1 = apply_chord_tensor_to_snapshot(snap0, parsed, enriched_img, f_bond)
    assert dec1.should_wake is True
    assert "被画成蓝发女仆的羞恼" in dec1.reason
    assert "源头:冰色" in snap1.inner_thought

    # 4. Cringe-flirt polarity inversion on disliked speaker (affinity < 30): annoyance++
    low_bond = SocialBondProfile(
        chat_key="group:10002002",
        user_id="9999",
        user_name="油腻路人",
        affinity_score=15.0,
        trust_score=0.60,
    )
    snap_cringe, _ = apply_chord_tensor_to_snapshot(
        snap0, parsed, enriched_img, low_bond
    )
    assert snap_cringe.affect.irritation > snap1.affect.irritation

    # 5. SubconsciousChordProbe end-to-end with scripted LLM via CognitiveCoreFacade
    await container.memory_repo.upsert_social_bond(f_bond)
    llm = _ScriptedLlm([{"choices": [{"message": {"content": raw_chord}}]}])
    probe = SubconsciousChordProbe(llm)
    container.cognitive_facade.set_subconscious_probe(probe)
    dec_live = await container.cognitive_facade.evaluate_incoming(enriched_img)
    assert dec_live.should_wake is True and "被画成蓝发女仆的羞恼" in dec_live.reason

















