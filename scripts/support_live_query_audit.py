#!/usr/bin/env python
"""Audit manual support on recent real user queries, read-only."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import time
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.mind.ranker_fusion import unified_rank

ROOT = Path(__file__).resolve().parents[1]


def _queries(db: Path, chat_key: str, limit: int) -> list[str]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT text FROM chat_messages WHERE chat_key=? AND is_self=0 "
        "AND text != '' ORDER BY id DESC LIMIT ?", (chat_key, limit),
    ).fetchall()
    return [str(row[0]) for row in rows]


async def run(db_path: Path, chat_key: str, limit: int) -> dict[str, object]:
    db = SqliteDatabase(db_path)
    await db.initialize()
    facts = await SqliteMemoryRepository(db).get_semantic_facts(chat_key)
    traits = await SqliteTraitShadowStore(db).active_traits()
    scores = await SqliteTraitMemoryLinkStore(db).ranker_scores(
        tuple(trait.trait_id for trait in traits)
    )
    now = int(time.time() * 1000)
    rows: list[dict[str, object]] = []
    improved = unchanged = worsened = 0
    for query in _queries(db_path, chat_key, limit):
        before = unified_rank(facts, query, {}, {}, now)
        after = unified_rank(facts, query, {}, {}, now, trait_scores=scores)
        before_ids = [fact.fact_id for fact in before]
        after_ids = [fact.fact_id for fact in after]
        movement = {}
        for memory_id in scores:
            old = before_ids.index(memory_id) + 1 if memory_id in before_ids else None
            new = after_ids.index(memory_id) + 1 if memory_id in after_ids else None
            movement[str(memory_id)] = {"before": old, "after": new}
            if old is not None and new is not None and new < old:
                improved += 1
            elif old == new:
                unchanged += 1
            else:
                worsened += 1
        rows.append({"query": query[:60], "movement": movement})
    return {
        "queries": len(rows), "improved": improved, "unchanged": unchanged,
        "worsened": worsened, "support_memories": sorted(scores), "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--chat-key", default="group:813506156")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "eval" / "baselines" / "support-live-queries-2026-11-01.json",
    )
    args = parser.parse_args()
    report = asyncio.run(run(args.db, args.chat_key, args.limit))
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
