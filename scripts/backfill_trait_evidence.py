#!/usr/bin/env python
"""Dry-run/apply real image-turn evidence from turn_traces (no synthetic quotes)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.trait_trace_backfill import candidates_from_rows

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--trait-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    await db.initialize()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    trait = con.execute(
        "SELECT id, chat_key, trait_text FROM persona_traits WHERE id=?",
        (args.trait_id,),
    ).fetchone()
    if trait is None:
        print("trait not found")
        return 1
    evidence_store = SqliteTraitEvidenceStore(db)
    existing = await evidence_store.list_trait_evidence(args.trait_id, 2000)
    existing_days = {item.created_ms // 86_400_000 for item in existing}
    rows = list(con.execute(
        "SELECT turn_id, chat_key, ts, steps_json FROM turn_traces "
        "WHERE chat_key=? AND steps_json LIKE '%look_at_image%' ORDER BY ts",
        (str(trait["chat_key"]),),
    ))
    candidates = candidates_from_rows(rows, existing_days)
    payload = {
        "trait_id": args.trait_id, "trait_text": trait["trait_text"],
        "existing_contexts": len({item.context_hash for item in existing}),
        "candidates": [
            {"turn_id": item.turn_id, "event_ms": item.event_ms,
             "context_hash": item.context_hash, "quote": item.quote}
            for item in candidates
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.apply:
        return 0
    for item in candidates:
        await evidence_store.record_trait_evidence(TraitEvidence(
            trait_id=args.trait_id, session_id=item.turn_id, turn_id=item.turn_id,
            quote=item.quote, quote_kind="assistant", polarity=1,
            context_hash=item.context_hash, created_ms=item.event_ms,
        ))
    status = await evidence_store.refresh_lifecycle(args.trait_id)
    print(f"applied={len(candidates)} status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
