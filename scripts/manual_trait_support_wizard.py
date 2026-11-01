#!/usr/bin/env python
"""Interactive manual support annotation: choose numbers, no ids to remember."""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import time
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore

ROOT = Path(__file__).resolve().parents[1]


def _ask(prompt: str) -> str:
    return input(prompt).strip()


def _pick(items: list[tuple[int, str]], title: str) -> int | None:
    print(f"\n{title}")
    for index, (_, label) in enumerate(items, 1):
        print(f"{index}. {label}")
    raw = _ask("输入编号（回车取消）：")
    if not raw:
        return None
    try:
        chosen = int(raw)
    except ValueError:
        return None
    return items[chosen - 1][0] if 1 <= chosen <= len(items) else None


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    args = parser.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    traits = [
        (int(row["id"]), f"{row['trait_text']} [{row['status']}]")
        for row in con.execute(
            "SELECT id, trait_text, status FROM persona_traits "
            "WHERE status='active' ORDER BY id"
        )
    ]
    trait_id = _pick(traits, "选择 trait")
    if trait_id is None:
        print("已取消")
        return 1
    evidence = [
        (int(row["id"]), str(row["quote"])[:90])
        for row in con.execute(
            "SELECT id, quote FROM trait_evidence WHERE trait_id=? "
            "ORDER BY created_ms DESC, id DESC LIMIT 20", (trait_id,),
        )
    ]
    evidence_id = _pick(evidence, "选择 evidence（她对那段经历的真实表述）")
    if evidence_id is None:
        print("已取消")
        return 1
    keyword = _ask("输入关键词筛选 memory（可空，直接回车显示最近 30 条）：")
    like = f"%{keyword}%"
    memories = [
        (int(row["id"]), f"{row['subject']}：{row['fact_text'][:90]}")
        for row in con.execute(
            "SELECT id, subject, fact_text FROM semantic_facts "
            "WHERE (? = '' OR subject LIKE ? OR fact_text LIKE ?) "
            "ORDER BY id DESC LIMIT 30",
            (keyword, like, like),
        )
    ]
    memory_id = _pick(memories, "选择 memory（这条证据支持的记忆）")
    if memory_id is None:
        print("已取消")
        return 1
    reason = _ask("写一句确认理由：") or "手动确认支持关系"
    print(f"\n将写入：trait={trait_id}, evidence={evidence_id}, memory={memory_id}")
    print(f"理由：{reason}")
    if _ask("确认写入？输入 y 确认，其他取消：").lower() != "y":
        print("已取消，未写入")
        return 0
    db = SqliteDatabase(args.db)
    await db.initialize()
    await SqliteTraitMemoryLinkStore(db).upsert_manual_support(
        trait_id, memory_id, reason, int(time.time() * 1000),
    )
    print("已写入 support link；ranker 会立即使用它。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
