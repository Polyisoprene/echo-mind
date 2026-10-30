"""Stage 29 A2c: history backfill reconstructs counters from chat_messages."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from echomind.adapters.storage.bond_depth_repo import SqliteBondDepthStore
from echomind.adapters.storage.database import SqliteDatabase
from echomind.mind.bond_features import depth_from_stats


async def test_backfill_reconstructs_counters(tmp_path: Path) -> None:
    db_path = tmp_path / "hist.db"
    db = SqliteDatabase(db_path)
    await db.initialize()
    store = SqliteBondDepthStore(db)
    await store.ensure_schema()

    conn = sqlite3.connect(str(db_path))
    rows = [
        # (mid, ts, sender, is_self, text): u1 speaks, she replies, u1 replies back
        ("1", 1_000, "u1", 0, "在吗"),
        ("2", 2_000, "__self__", 1, "在呀"),
        ("3", 3_000, "u1", 0, "那陪我聊聊"),
        ("4", 4_000, "u2", 0, "我也在"),
        ("5", 5_000, "__self__", 1, "一起"),
        ("6", 6_000, "u1", 0, "好"),
    ]
    with conn:
        conn.executemany(
            "INSERT INTO chat_messages (chat_key, mid, ts, sender_id, sender_name, is_self, "
            "text, media_json) VALUES ('group:A', ?, ?, ?, ?, ?, ?, '[]')",
            [(mid, ts, sender, sender, is_self, text) for mid, ts, sender, is_self, text in rows],
        )
    conn.close()

    await store.backfill_from_history()
    u1 = await store.get_stats("group:A", "u1")
    assert u1 is not None
    # her_msgs 只统计"她对这个人"的回复（她一共回了两条：对 u1、对 u2 各一条）
    assert u1.msgs == 3 and u1.her_msgs == 1
    assert u1.replies_to_them >= 1
    assert u1.responded_to_her >= 1
    assert depth_from_stats(u1) > 0

    u2 = await store.get_stats("group:A", "u2")
    assert u2 is not None and u2.msgs == 1
