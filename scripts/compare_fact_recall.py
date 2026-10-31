"""Compare legacy fact recall with the claim-based ranking on real chat queries."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path

from echomind.adapters.storage.claim_views import load_claim_views
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.mind.fact_shadow import claim_rank, compare
from echomind.mind.ranker_fusion import unified_rank

LIMIT = 28


async def main() -> None:
    data_dir = Path(os.getenv("ECHOMIND_DATA_DIR", "data"))
    chat = os.getenv("ECHOMIND_CHAT_KEY", "group:813506156")
    db = SqliteDatabase(data_dir / "echomind.db")
    repo = SqliteMemoryRepository(db)
    facts = await repo.get_semantic_facts(chat)
    views = await load_claim_views(db, chat)
    con = sqlite3.connect(f"file:{data_dir / 'echomind.db'}?mode=ro", uri=True)
    queries = [r[0] for r in con.execute(
        "SELECT text FROM chat_messages WHERE chat_key=? AND is_self=0 "
        "ORDER BY ts DESC LIMIT 30", (chat,))]
    now = con.execute("SELECT MAX(ts) FROM chat_messages").fetchone()[0] or 0

    locked_keys = {_key(v) for v in views if v.locked}
    results = []
    locked_keep = {"legacy": 0, "claims": 0}
    for query in queries:
        legacy = [_key(f) for f in unified_rank(tuple(facts), query, {}, {}, now)[:LIMIT]]
        claims = claim_rank(views, query, LIMIT, now)
        results.append({"query": query[:40], **compare(legacy, claims)})
        locked_keep["legacy"] += len(locked_keys & set(legacy))
        locked_keep["claims"] += len(locked_keys & set(claims))
    ratios = [r["ratio"] for r in results]
    summary = {
        "queries": len(results), "facts": len(facts), "claims": len(views),
        "locked_facts": len(locked_keys),
        "avg_overlap_ratio": round(sum(ratios) / max(1, len(ratios)), 3),
        "min_ratio": round(min(ratios), 3) if ratios else 0,
        "locked_hits_per_query": {
            k: round(v / max(1, len(results)), 2) for k, v in locked_keep.items()},
        "queries_with_zero_overlap": sum(1 for r in results if r["overlap"] == 0),
        "example": {k: results[0][k] for k in ("query", "overlap", "ratio")} if results else {},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _key(fact: object) -> str:
    return f"{getattr(fact, 'subject', '')}：{getattr(fact, 'fact_text', '')}"


if __name__ == "__main__":
    asyncio.run(main())
