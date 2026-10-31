#!/usr/bin/env python
"""Extract typed relations from semantic facts and persist them (P2)."""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
from collections import Counter
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.relation_repo import SqliteRelationStore
from echomind.domain.relation import MemoryRelation
from echomind.mind.relation_extractor import extract

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = conn.execute("SELECT subject, fact_text FROM semantic_facts ORDER BY id").fetchall()
    candidates = []
    for subject, text in rows:
        candidates.extend(extract(str(subject), str(text)))
    counts = Counter(candidate.predicate for candidate in candidates)
    print(f"facts={len(rows)} relations={len(candidates)} predicates={dict(counts)}")
    for candidate in candidates[:20]:
        print(f"  {candidate.subject} --{candidate.predicate}--> {candidate.object}")
    if not args.apply:
        print("dry-run: pass --apply to write")
        return 0
    db = SqliteDatabase(args.db)
    await db.initialize()
    store = SqliteRelationStore(db)
    for candidate in candidates:
        await store.upsert(MemoryRelation(
            subject_id=candidate.subject, predicate=candidate.predicate,
            object_id=candidate.object, confidence=candidate.confidence,
        ))
    print(f"applied {len(candidates)} relations")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
