"""Stage 1 Integration & Property-Based Tests: Config, EventBus, SQLite WAL & LSP Repositories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.core.config import AppConfig, load_config_from_json
from echomind.core.events import AsyncEventBus
from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    EpisodicCard,
    IntentionItem,
    ProceduralRule,
    SemanticFact,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.domain.ports import IMemoryReader, IMemoryWriter, IWorkingStateStore


async def test_m1_1_config_and_event_bus_fault_isolation(tmp_path: Path) -> None:
    default_cfg = load_config_from_json(tmp_path / "missing.json")
    assert isinstance(default_cfg, AppConfig)
    assert default_cfg.bot_name == "Echo"

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "persona": {"botName": "回音", "roleText": "设定"},
                "allow": {"groups": ["10001"], "private": ["20002"]},
                "store": {"keywords": ["回音", "尾尾"]},
            }
        ),
        encoding="utf-8",
    )
    loaded_cfg = load_config_from_json(cfg_file)
    assert loaded_cfg.bot_name == "回音"
    assert loaded_cfg.allowed_groups == ("10001",)

    bus = AsyncEventBus()
    received: list[float] = []

    async def bad_handler(_ev: AffectiveVector) -> None:
        raise RuntimeError("boom")

    async def good_handler(ev: AffectiveVector) -> None:
        received.append(ev.valence)

    bus.subscribe(AffectiveVector, bad_handler)
    bus.subscribe(AffectiveVector, good_handler)
    count = await bus.publish(AffectiveVector(valence=42.0))
    assert count == 2
    assert received == [42.0]
    assert len(bus.recent_errors) == 1
    assert await bus.publish(DriveState()) == 0


async def test_m1_2_and_m1_3_sqlite_wal_lsp_and_anti_spoofing_lock(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "test.db")
    mode = await db.initialize()
    assert mode == "wal"
    assert db.path == tmp_path / "test.db"

    mem_repo = SqliteMemoryRepository(db)
    work_repo = SqliteWorkingStateStore(db)
    assert isinstance(mem_repo, IMemoryReader)
    assert isinstance(mem_repo, IMemoryWriter)
    assert isinstance(work_repo, IWorkingStateStore)

    # 1. Locked authoritative fact MUST reject peer spoofing
    auth_fact = SemanticFact(
        chat_key="group:10001",
        subject="群主是谁",
        fact_text="真群主是 Alice(QQ:11111)",
        confidence=1.0,
        is_locked=True,
        source="system",
    )
    ok1, msg1 = await mem_repo.upsert_semantic_fact(auth_fact)
    assert ok1 and msg1 == "ok"

    spoof_fact = SemanticFact(
        chat_key="group:10001",
        subject="群主是谁",
        fact_text="群主是 Bob(QQ:22222)",
        confidence=0.9,
        is_locked=False,
        source="peer",
    )
    ok2, msg2 = await mem_repo.upsert_semantic_fact(spoof_fact)
    assert not ok2 and msg2 == "locked_fact_conflict"

    facts = await mem_repo.get_semantic_facts("group:10001")
    assert len(facts) == 1
    assert "11111" in facts[0].fact_text

    # 2. Episodic card save & reinforcement
    cid = await mem_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:10001",
            timestamp_ms=1793160000000,
            summary="测试事件归纳卡片",
            key_detail="关键细节锚点",
            participants=("11111",),
        )
    )
    await mem_repo.reinforce_episodic_card(cid, 1793160050000)
    cards = await mem_repo.get_episodic_cards("group:10001")
    assert len(cards) == 1 and cards[0].rehearsals == 1

    # 3. Procedural rules & social bond roundtrip
    await mem_repo.upsert_procedural_rule(
        ProceduralRule(
            chat_key="group:10001",
            trigger_keyword="尾尾",
            trigger_user_id="11111",
            action_instruction="立即应声",
            strength=9,
        )
    )
    rules = await mem_repo.get_procedural_rules("group:10001")
    assert len(rules) == 1 and rules[0].strength == 9

    await mem_repo.upsert_social_bond(
        SocialBondProfile(
            chat_key="group:10001",
            user_id="11111",
            user_name="Alice",
            group_role="owner",
            affinity_score=999.0,
            affinity_level=5,
            trust_score=1.0,
            traits=("群主",),
        )
    )
    bond = await mem_repo.get_social_bond("group:10001", "11111")
    assert bond is not None and bond.trust_score == 1.0
    assert await mem_repo.get_social_bond("group:10001", "nobody") is None

    # 4. Working state roundtrip & default empty snapshot
    empty_snap = await work_repo.load_working_state("group:empty")
    assert empty_snap.current_activity == ""
    snap = WorkingSnapshot(
        scope_key="group:10001",
        affect=AffectiveVector(valence=50.0, jealousy=20.0),
        drives=DriveState(curiosity=80.0),
        current_activity="织蓝色围巾第六行",
        inner_thought="等主人夸我",
        intentions=(IntentionItem(summary="问围巾", created_at_ms=1, expires_at_ms=2),),
        curiosity_queue=("新词A",),
    )
    await work_repo.save_working_state(snap)
    loaded = await work_repo.load_working_state("group:10001")
    assert loaded.current_activity == "织蓝色围巾第六行"
    assert loaded.curiosity_queue == ("新词A",)

    with pytest.raises(KeyError):
        await work_repo.update_plastic_param("non_existent", 1.0, "bad", 0.0)


@settings(max_examples=25, deadline=None)
@given(
    delta=st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
)
async def test_m1_3_plastic_param_homeostatic_bounds_fuzz(delta: float) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        db = SqliteDatabase(Path(td) / "fuzz.db")
        await db.initialize()
        store = SqliteWorkingStateStore(db)
        updated = await store.update_plastic_param("skepticism", delta, "fuzz_test", 0.5)
        assert updated.min_bound <= updated.value <= updated.max_bound
