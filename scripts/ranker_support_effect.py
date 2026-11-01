#!/usr/bin/env python
"""Read-only comparison of lexical fusion with and without trait support."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.mind.ranker_fusion import unified_rank

ROOT = Path(__file__).resolve().parents[1]


async def run(db_path: Path, chat_key: str, query: str) -> dict[str, object]:
    db = SqliteDatabase(db_path)
    await db.initialize()
    from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
    facts = await SqliteMemoryRepository(db).get_semantic_facts(chat_key)
    traits = await SqliteTraitShadowStore(db).active_traits()
    scores = await SqliteTraitMemoryLinkStore(db).ranker_scores(
        tuple(trait.trait_id for trait in traits)
    )
    now = int(time.time() * 1000)
    base = unified_rank(facts, query, {}, {}, now)
    with_trait = unified_rank(facts, query, {}, {}, now, trait_scores=scores)
    ids = [359, 361]
    def positions(ranked: tuple[object, ...]) -> dict[int, int]:
        order = [fact.fact_id for fact in ranked]
        return {item: order.index(item) + 1 for item in ids if item in order}
    return {
        "chat_key": chat_key, "query": query, "facts": len(facts),
        "support_scores": scores, "before": positions(base),
        "after": positions(with_trait),
        "top_before": [fact.fact_id for fact in base[:5]],
        "top_after": [fact.fact_id for fact in with_trait[:5]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--chat-key", default="group:813506156")
    parser.add_argument("--query", default="回音唱歌 老婆 嘴硬")
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "eval" / "baselines" / "ranker-support-2026-11-01.json",
    )
    args = parser.parse_args()
    report = asyncio.run(run(args.db, args.chat_key, args.query))
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
