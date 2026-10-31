"""Stage 5 Integration Tests: Composition Root (EchoMindContainer) & FastAPI Inspector API."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.core.bootstrap import EchoMindContainer
from echomind.core.config import GatewayEndpointConfig
from echomind.domain.models import (
    DriveState,
    EpisodicCard,
    SemanticFact,
    SocialBondProfile,
    TurnRecord,
    TurnStep,
    WorkingSnapshot,
)
from echomind.web.app import create_web_app


async def test_ac5_1_to_ac5_5_bootstrap_and_fastapi_mind_inspector(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(
        db_path=tmp_path / "web_mind.db",
        operator_ids=("10001001",),
        default_chat_key="group:10002002",
    )
    await container.memory_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:10002002",
            timestamp_ms=1793160000000,
            summary="测试情景记忆卡片",
            key_detail="细节锚点123",
            pinned=True,
        )
    )
    await container.memory_repo.upsert_social_bond(
        SocialBondProfile(
            chat_key="group:10002002",
            user_id="10004004",
            user_name="馍馍",
            group_role="owner",
            affinity_score=88.0,
        )
    )
    await container.working_store.save_working_state(
        WorkingSnapshot(
            scope_key="global", drives=DriveState(curiosity=65.0), curiosity_queue=("飞飞鼠",)
        )
    )

    app = create_web_app(container, config_path=tmp_path / "config.json")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # AC-5.5: GET / HTML console page
        r_html = await client.get("/")
        assert r_html.status_code == 200
        assert "EchoMind" in r_html.text and "认知控制台" in r_html.text

        # AC-5.2: POST /api/mind/facts locks an authoritative fact
        r_fact = await client.post(
            "/api/mind/facts",
            json={
                "chat_key": "group:10002002",
                "subject": "本群真实群主",
                "fact_text": "馍馍(10004004)",
                "is_locked": True,
            },
        )
        assert r_fact.status_code == 200 and r_fact.json()["ok"] is True

        # Verify peer spoofing is rejected by locked fact!
        ok_spoof, reason = await container.memory_repo.upsert_semantic_fact(
            SemanticFact(
                chat_key="group:10002002",
                subject="本群真实群主",
                fact_text="假群主",
                source="peer",
            )
        )
        assert ok_spoof is False and reason == "locked_fact_conflict"

        # AC-5.4: POST /api/mind/plastic/tune & POST /api/mind/tick
        r_tune = await client.post(
            "/api/mind/plastic/tune",
            json={"key": "persona_guile", "delta": 5.0, "reason": "手动提升小机灵鬼度"},
        )
        assert r_tune.status_code == 200
        assert r_tune.json()["param"]["value"] == 54.0
        assert r_tune.json()["applied"] == 2.0, "console tuning must respect the clip"

        r_tick = await client.post("/api/mind/tick")
        assert r_tick.status_code == 200
        assert r_tick.json()["triggered"] is True
        assert r_tick.json()["proposal"]["drive_kind"] == "curiosity_explore"

        # AC-5.1: GET /api/mind/snapshot returns complete 12-layer state
        r_snap = await client.get("/api/mind/snapshot")
        assert (await client.get("/api/mind/persona-card")).status_code == 200
        assert (
            await client.put(
                "/api/mind/persona-card", json={"bot_name": "回音", "role_text": "设定"}
            )
        ).status_code == 200
        assert (
            await client.put(
                "/api/mind/bonds/1001", json={"affinity_score": 150.0, "user_name": "测试"}
            )
        ).status_code == 200
        assert (await client.get("/api/mind/skills/configs")).status_code == 200
        assert (await client.post("/api/mind/skills/web_search/toggle")).status_code == 200
        assert (await client.delete("/api/mind/skills/web_search")).status_code == 200
        assert (await client.post("/api/mind/skills/restore")).status_code == 200
        assert r_snap.status_code == 200
        data = r_snap.json()
        assert data["ok"] is True
        assert len(data["facts"]) == 1
        assert len(data["episodic"]) == 1
        assert len(data["bonds"]) == 1
        assert "persona_guile" in data["plastic_params"]
        assert len(data["plastic_logs"]) >= 1

        # AC-5.3: DELETE /api/mind/episodic/{card_id}
        cid = data["episodic"][0]["card_id"]
        r_del = await client.delete(f"/api/mind/episodic/{cid}")
        assert r_del.status_code == 200 and r_del.json()["deleted_card_id"] == cid

        r_snap2 = await client.get("/api/mind/snapshot")
        assert len(r_snap2.json()["episodic"]) == 0


async def test_ac5_6_console_api_sessions_memory_persona_probe_and_logs(tmp_path: Path) -> None:
    log_file = tmp_path / "console.log"
    log_file.write_text("INFO: boot ok\n[EchoMind] ws connected\n", encoding="utf-8")
    container = await EchoMindContainer.create(db_path=tmp_path / "console.db")
    app = create_web_app(container, log_path=log_file, config_path=tmp_path / "config.json")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with container.db.connect() as conn:
            await conn.execute(
                "INSERT INTO chat_messages "
                "(chat_key, mid, ts, sender_id, sender_name, is_self, text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("group:10002002", "m1", 1793000000000, "10001001", "主人", 0, "尾尾在吗"),
            )
            await conn.execute(
                "INSERT INTO chat_messages "
                "(chat_key, mid, ts, sender_id, sender_name, is_self, text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("group:10002002", "m2", 1793000001000, "10003003", "回音", 1, "在呢"),
            )
            await conn.execute(
                "INSERT INTO stickers (id, desc_text, use_count) VALUES (?, ?, ?)",
                ("s1", "开心鲸鱼", 7),
            )
            await conn.execute(
                "INSERT INTO llm_traces (ts, session_id, gateway_name, model_name, elapsed_ms, "
                "prompt_tokens, cached_tokens, completion_tokens, is_failover) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    int(time.time() * 1000),
                    "s",
                    "PrimaryGateway",
                    "deepseek-v4.1-flash",
                    1200,
                    900,
                    400,
                    60,
                ),
            )
            await conn.commit()

        sessions = (await client.get("/api/mind/sessions")).json()
        assert sessions["ok"] is True and sessions["sessions"][0]["total"] == 2

        msgs = (await client.get("/api/mind/messages?limit=10")).json()
        assert [m["text"] for m in msgs["messages"]] == ["尾尾在吗", "在呢"]

        stickers = (await client.get("/api/mind/stickers")).json()
        assert stickers["stickers"][0]["desc"] == "开心鲸鱼"

        usage = (await client.get("/api/mind/usage")).json()
        assert usage["usage"]["calls"] == 1 and usage["usage"]["prompt"] == 900

        logs = (await client.get("/api/mind/logs?lines=10")).json()
        assert any("EchoMind" in line for line in logs["lines"])

        runtime = (await client.get("/api/mind/runtime")).json()
        assert runtime["ok"] is True

        assert (await client.post("/api/mind/bans", json={"phrase": "诶"})).json()["ok"] is True
        bans = (await client.get("/api/mind/bans")).json()
        assert [b["phrase"] for b in bans["bans"]] == ["诶"]
        await client.delete("/api/mind/bans/%E8%AF%B6")
        assert (await client.get("/api/mind/bans")).json()["bans"] == []

        probe = (
            await client.post(
                "/api/mind/probe", json={"text": "你是不是吃醋了", "sender_id": "10001001"}
            )
        ).json()
        assert probe["ok"] is True
        assert "回音此刻的认知与内心状态" in probe["rendered_mind_block"]
        assert probe["attention"]["should_wake"] is True

        async with container.db.connect() as conn:
            await conn.execute(
                "INSERT INTO persona_traits (category, trait_text, strength, created_at) "
                "VALUES ('habit', '爱查梗', 5, 1)"
            )
            await conn.commit()
        traits = (await client.get("/api/mind/traits")).json()
        assert traits["traits"][0]["text"] == "爱查梗"
        assert "status" in traits["traits"][0]
        assert "evidence_count" in traits["traits"][0]
        tid = traits["traits"][0]["id"]
        evidence = (await client.get(f"/api/mind/traits/{tid}/evidence")).json()
        assert evidence["ok"] is True and evidence["evidence"] == []
        health = (await client.get("/api/mind/trait-health")).json()
        assert health["ok"] is True
        assert health["status"] in {
            "no_active", "waiting_turn", "shadow_missing_trait",
            "no_causal_links", "ok",
        }
        assert (await client.delete(f"/api/mind/traits/{tid}")).json()["ok"] is True


async def test_ac5_7_llm_config_hot_reload_and_per_request_traces(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "api": {
                    "baseUrl": "http://a.example/v1",
                    "apiKey": "sk-abcdef1234567890",
                    "model": "model-alpha",
                    "temperature": 0.5,
                }
            }
        ),
        encoding="utf-8",
    )
    container = await EchoMindContainer.create(db_path=tmp_path / "llm.db")
    gateway = FailoverLlmGateway(
        GatewayEndpointConfig(name="P", base_url="http://a.example/v1", model="model-alpha"),
        GatewayEndpointConfig(name="F", base_url="http://b.example/v1", model="model-beta"),
        container.db,
    )
    container.llm_gateway = gateway
    app = create_web_app(container, config_path=cfg_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = (await client.get("/api/mind/llm")).json()
        assert first["primary"]["model"] == "model-alpha"
        assert first["primary"]["api_key_masked"].startswith("sk-abc")
        assert first["temperature"] == 0.5

        moved = (
            await client.put(
                "/api/mind/llm",
                json={
                    "model": "model-gamma",
                    "base_url": "http://c.example/v1",
                    "temperature": 0.9,
                },
            )
        ).json()
        assert moved["applied"] is True
        assert moved["primary"]["model"] == "model-gamma"
        primary, _fallback = gateway.endpoints()
        assert primary.model == "model-gamma" and primary.base_url == "http://c.example/v1"

        async with container.db.connect() as conn:
            await conn.execute(
                "INSERT INTO llm_traces (ts, session_id, gateway_name, model_name, elapsed_ms, "
                "prompt_tokens, cached_tokens, completion_tokens, is_failover, chat_key) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    1793000000000,
                    "s1",
                    "PrimaryGateway",
                    "model-gamma",
                    800,
                    120,
                    40,
                    30,
                    0,
                    "group:1",
                ),
            )
            await conn.commit()
        traces = (await client.get("/api/mind/llm/traces?limit=5")).json()["traces"]
        assert traces[0]["chat_key"] == "group:1"
        assert traces[0]["model"] == "model-gamma"

        assert (await client.get("/api/mind/runtime")).json()["model"] == "model-gamma"


async def test_ac5_8_turn_timeline_captures_every_llm_and_tool_step(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "turns.db")
    app = create_web_app(container, config_path=tmp_path / "config.json")
    transport = httpx.ASGITransport(app=app)

    record = TurnRecord(
        turn_id="t1",
        chat_key="group:1",
        ts=1793000000000,
        trigger="橡皮：我是谁呀",
        rounds=2,
        sent_count=1,
        total_ms=3200,
        model="model-z",
        steps=(
            TurnStep(seq=1, kind="llm", name="model-z", detail="4139→68 tok", elapsed_ms=1800),
            TurnStep(
                seq=2,
                kind="tool",
                name="send_message",
                detail='{"messages":["在呢"]}',
                elapsed_ms=12,
            ),
            TurnStep(seq=3, kind="llm", name="model-z", detail="4200→45 tok", elapsed_ms=900),
        ),
    )
    await container.trace_store.save_turn(record)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        data = (await client.get("/api/mind/turns?chat_key=group:1")).json()
        turns = data["turns"]
        assert len(turns) == 1
        assert turns[0]["rounds"] == 2
        assert [s["kind"] for s in turns[0]["steps"]] == ["llm", "tool", "llm"]
        assert turns[0]["steps"][1]["name"] == "send_message"


async def test_ext_routers_endpoints(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "ext.db")
    app = create_web_app(container, config_path=tmp_path / "cfg.json")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        assert (await client.get("/api/mind/persona-card")).status_code == 200
        assert (
            await client.put(
                "/api/mind/persona-card", json={"bot_name": "回音", "role_text": "设定"}
            )
        ).status_code == 200
        assert (
            await client.put(
                "/api/mind/bonds/1001", json={"affinity_score": 150.0, "user_name": "测试"}
            )
        ).status_code == 200
        assert (await client.get("/api/mind/skills/configs")).status_code == 200
        assert (
            await client.put("/api/mind/skills/configs/bili", json={"values": {"sessdata": "x"}})
        ).status_code == 200
        assert (await client.post("/api/mind/skills/web_search/toggle")).status_code == 200
        assert (await client.delete("/api/mind/skills/web_search")).status_code == 200
        assert (await client.post("/api/mind/skills/restore")).status_code == 200
        assert (await client.get("/api/mind/voice")).status_code == 200
