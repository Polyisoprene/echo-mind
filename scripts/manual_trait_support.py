#!/usr/bin/env python
"""Explicitly annotate one trait evidence -> memory support link (dry-run default)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import time
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore

ROOT = Path(__file__).resolve().parents[1]


def _row(db: Path, sql: str, params: tuple[object, ...]) -> sqlite3.Row | None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con.execute(sql, params).fetchone()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--trait-id", type=int, required=True)
    parser.add_argument("--evidence-id", type=int, required=True)
    parser.add_argument("--memory-id", type=int, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    evidence = _row(
        args.db,
        "SELECT id, trait_id, quote, turn_id FROM trait_evidence WHERE id=?",
        (args.evidence_id,),
    )
    fact = _row(
        args.db,
        "SELECT id, subject, fact_text FROM semantic_facts WHERE id=?",
        (args.memory_id,),
    )
    if evidence is None or fact is None:
        print("evidence or semantic fact not found")
        return 1
    if int(evidence["trait_id"]) != args.trait_id:
        print("evidence does not belong to trait")
        return 1
    if not args.reason.strip():
        print("reason is required")
        return 1
    payload = {
        "trait_id": args.trait_id, "evidence_id": args.evidence_id,
        "memory_id": args.memory_id, "quote": evidence["quote"],
        "memory": f"{fact['subject']}：{fact['fact_text']}",
        "reason": args.reason.strip(), "applied": args.apply,
    }
    if args.apply:
        db = SqliteDatabase(args.db)
        await db.initialize()
        await SqliteTraitMemoryLinkStore(db).upsert_manual_support(
            args.trait_id, args.memory_id, args.reason.strip(),
            int(time.time() * 1000),
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
