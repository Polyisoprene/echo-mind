"""Stage 28 replay harness contract: deterministic, zero-LLM, chord-driven rewards."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer

ROOT = Path(__file__).resolve().parents[2]
CK = "group:10002002"
OWNER = "10001001"
DETERMINISTIC_KEYS = (
    "turns", "wakes", "probe_calls", "cache_peak", "double_apply",
    "reward_samples", "reward_spread", "bond_deltas",
)


def _make_db(path: Path, uid: str, name: str, text: str) -> None:
    """Seed a one-message synthetic history so polarity can be measured in isolation."""

    async def _seed() -> None:
        await EchoMindContainer.create(db_path=path, owner_qq=OWNER, default_chat_key=CK)
        conn = sqlite3.connect(str(path))
        with conn:
            conn.execute(
                "INSERT INTO chat_messages (id, chat_key, mid, ts, sender_id, sender_name, "
                "is_self, text, media_json) VALUES (?, ?, ?, ?, ?, ?, 0, ?, '[]')",
                (1, CK, "1", 1_700_000_000_000, uid, name, text),
            )
        conn.close()

    asyncio.run(_seed())


def _run(db: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    # A subprocess isolates the replay harness' frozen clock & module-level spies.
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable, "scripts/replay_eval.py",
            "--db", str(db), "--work-db", str(out / "sandbox.db"),
            "--fixture", "tests/fixtures/chords_stage28.json",
            "--chat-key", CK, "--owner", OWNER, "--turns", "5", "--out", str(out),
        ],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180, check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    reports = sorted(out.glob("replay_*.json"))
    assert reports, "replay report missing"
    data: dict[str, Any] = json.loads(reports[-1].read_text(encoding="utf-8"))
    return data


def test_rg_replay_harness_deterministic_and_chord_driven(tmp_path: Path) -> None:
    """Replay is reproducible, LLM-free, and reward polarity follows the recorded chord."""
    insult_db = tmp_path / "insult.db"
    praise_db = tmp_path / "praise.db"
    _make_db(insult_db, "2005", "挑衅者", "你这蠢AI，快给我闭嘴")
    _make_db(praise_db, "2006", "好朋友", "你真棒好乖，谢谢你")

    first = _run(insult_db, tmp_path / "a1")
    second = _run(insult_db, tmp_path / "a2")
    for key in DETERMINISTIC_KEYS:
        assert first[key] == second[key], f"non-deterministic metric: {key}"

    assert first["probe_calls"] >= 1, "fixture probe must be exercised"
    assert first["wakes"] >= 1, "the summoning message must wake"
    assert first["cache_limit_ok"] is True
    assert first["reward_spread"] >= 0.0

    assert first["bond_deltas"]["2005"]["trust"] < 0, "insult must lower trust"
    praise = _run(praise_db, tmp_path / "b1")
    assert praise["bond_deltas"]["2006"]["trust"] > 0, "praise must raise trust"
