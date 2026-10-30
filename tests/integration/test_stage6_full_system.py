"""Stage 6 Full-System End-to-End Acceptance Test: Reminders, CraniMem Pruning & Production App."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from echomind.adapters.onebot.bot_bridge import OneBotV11Bridge
from echomind.domain.models import EpisodicCard, Percept
from echomind.main import create_production_app
from echomind.runtime.agent_runner import AgentSessionRunner
from echomind.runtime.prompt_composer import PromptComposer
from echomind.runtime.scheduler import CognitiveHeartbeatScheduler
from echomind.tools.messaging_and_group import GetGroupMembersTool, SendMessageTool


class FullSystemFakeCaller:
    def __init__(self) -> None:
        self.sent_payloads: list[tuple[str, dict[str, Any]]] = []
        self._seq = 5000

    async def call_api(self, api: str, **data: Any) -> Any:
        self.sent_payloads.append((api, data))
        if api == "get_group_member_list":
            return [{"user_id": 10004004, "card": "馍馍", "nickname": "kira", "role": "owner"}]
        self._seq += 1
        return {"message_id": self._seq}


class FullSystemScriptedLlm:
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
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "<think>正常回复主人</think>明早八点的闹钟我记着呢，晚安呀~",
                    }
                }
            ]
        }


async def test_ac6_1_to_ac6_3_full_system_end_to_end_acceptance(tmp_path: Path) -> None:
    app, container = await create_production_app(db_path=tmp_path / "prod_e2e.db")
    caller = FullSystemFakeCaller()
    bridge = OneBotV11Bridge(caller, container.db)
    container.registry.register_tool(SendMessageTool(bridge))
    container.registry.register_tool(GetGroupMembersTool(bridge))

    scheduler = CognitiveHeartbeatScheduler(
        db=container.db,
        mem_reader=container.memory_repo,
        cognitive=container.cognitive_facade,
        sender=bridge,
    )

    base_ts = 1_700_000_000_000
    # 1. Seed a due reminder and an unexpired reminder in SQLite
    async with container.db.connect() as conn:
        await conn.execute(
            "INSERT INTO reminders (chat_key, target_user_id, remind_at_ms, content, fired) "
            "VALUES (?, ?, ?, ?, 0)",
            ("group:10002002", "10001001", base_ts - 1000, "明早八点叫主人起床"),
        )
        await conn.commit()

    # 2. Seed a pinned important card and a decayed low-utility noise card for CraniMem pruning
    keep_id = await container.memory_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:10002002",
            timestamp_ms=base_ts,
            summary="和主人约定织蓝色围巾",
            key_detail="第六行",
            importance=4.5,
            pinned=True,
        )
    )
    noise_id = await container.memory_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:10002002",
            timestamp_ms=base_ts - 100 * 3_600_000,
            summary="某条早已淡忘的无意义水贴",
            importance=1.2,
            pinned=False,
            rehearsals=0,
        )
    )

    # AC-6.1 & AC-6.2: Run heartbeat cycle (due reminder fires once + CraniMem prunes noise card!)
    _prop, fired_ids, pruned_ids = await scheduler.run_heartbeat_cycle("group:10002002", base_ts)
    assert len(fired_ids) == 1
    assert pruned_ids == (noise_id,)
    assert keep_id not in pruned_ids

    # Second check_due_reminders does not re-fire already fired reminder!
    assert await scheduler.check_due_reminders(base_ts) == ()

    # AC-6.3: Run full conversational turn through Enrichment -> CognitiveFacade -> AgentRunner
    raw_percept = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="8801",
        timestamp_ms=base_ts,
        sender_id="10001001",
        sender_name="L今晚早睡了吗",
        text="尾尾，晚安啦",
    )
    for sensor in container.registry.sensors:
        raw_percept = await sensor.enrich(raw_percept)
    assert raw_percept.is_called_by_name is True

    runner = AgentSessionRunner(
        cognitive=container.cognitive_facade,
        llm=FullSystemScriptedLlm(),
        registry=container.registry,
        sender=bridge,
        composer=PromptComposer(role_text="傲娇蓝发鲸鱼娘", bot_name="回音"),
    )
    outcome = await runner.run_turn("group:10002002", (), (raw_percept,), social_reward=0.9)
    assert outcome.sent_texts == ("明早八点的闹钟我记着呢，晚安呀~",)

    # Verify via FastAPI Cognitive Inspector that only the pinned card remains and warmth rose!
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/mind/snapshot")
        snap_data = resp.json()
        assert len(snap_data["episodic"]) >= 1
        assert any(c["card_id"] == keep_id for c in snap_data["episodic"])
        assert snap_data["plastic_params"]["persona_warmth"]["value"] > 65.0


async def test_ac6_4_live_onebot_event_parser_and_runtime_dispatch(tmp_path: Path) -> None:
    from echomind.adapters.onebot.enrichers import PerceptEnrichmentPipeline
    from echomind.adapters.onebot.event_parser import parse_onebot_event
    from echomind.adapters.onebot.live_client import OneBotLiveRuntime

    groups = frozenset({"10002002"})
    # 1. Group @me message
    ev_msg = {
        "post_type": "message",
        "message_type": "group",
        "group_id": 10002002,
        "user_id": 10001001,
        "message_id": 7701,
        "time": 1700000000,
        "sender": {"card": "L今晚早睡了吗"},
        "message": [
            {"type": "at", "data": {"qq": "10003003"}},
            {"type": "text", "data": {"text": " 尾尾晚安"}},
        ],
    }
    p1 = parse_onebot_event(ev_msg, "10003003", groups, ("10001001",))
    assert p1 is not None and p1.is_at_me is True and "尾尾晚安" in p1.text

    # 2. Poke event targeting bot
    ev_poke = {
        "post_type": "notice",
        "sub_type": "poke",
        "group_id": 10002002,
        "user_id": 10001001,
        "target_id": 10003003,
        "time": 1700000005,
    }
    p2 = parse_onebot_event(ev_poke, "10003003", groups, ("10001001",))
    assert p2 is not None and p2.is_poke_me is True

    # 3. Ignore self message or unauthorized group
    assert parse_onebot_event({**ev_msg, "user_id": 10003003}, "10003003", groups, ()) is None
    assert parse_onebot_event({**ev_msg, "group_id": 11111}, "10003003", groups, ()) is None

    # 4. End-to-end OneBotLiveRuntime.handle_raw_event
    _app, container = await create_production_app(db_path=tmp_path / "live_rt.db")
    caller = FullSystemFakeCaller()
    bridge = OneBotV11Bridge(caller, container.db)
    container.registry.register_tool(SendMessageTool(bridge))
    runner = AgentSessionRunner(
        cognitive=container.cognitive_facade,
        llm=FullSystemScriptedLlm(),
        registry=container.registry,
        sender=bridge,
        composer=PromptComposer(role_text="小鲸鱼", bot_name="回音"),
    )
    scheduler = CognitiveHeartbeatScheduler(
        container.db, container.memory_repo, container.cognitive_facade, bridge
    )
    rt = OneBotLiveRuntime(
        ws_url="ws://127.0.0.1:3001",
        access_token="",
        self_id="10003003",
        allowed_groups=("10002002",),
        operator_ids=("10001001",),
        db=container.db,
        pipeline=PerceptEnrichmentPipeline(container.registry.sensors),
        cognitive=container.cognitive_facade,
        runner=runner,
        scheduler=scheduler,
    )
    triggered = await rt.handle_raw_event(ev_msg)
    assert triggered is True
    assert len(caller.sent_payloads) >= 1
