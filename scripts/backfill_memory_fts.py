#!/usr/bin/env python
"""Backfill semantic facts into the standalone FTS5 index; no live read change."""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import time
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_fts import FtsMemoryIndex
from echomind.adapters.storage.memory_repo import FACT_COLUMNS
from echomind.adapters.storage.memory_rows import row_to_fact

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    await db.initialize()
    index = FtsMemoryIndex(db)
    await index.ensure_schema()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        f"SELECT {FACT_COLUMNS} FROM semantic_facts"  # noqa: S608
    ).fetchall()
    start = time.perf_counter()
    for row in rows:
        await index.upsert(row_to_fact(row))
    elapsed = time.perf_counter() - start
    print({"indexed": len(rows), "seconds": round(elapsed, 3)})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
