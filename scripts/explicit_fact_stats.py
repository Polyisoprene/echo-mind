#!/usr/bin/env python
"""Measure explicit-fact production from the stable '提到：' fact-text pattern."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from echomind.mind.trait_trace_backfill import DAY_MS

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT updated_at, source_turn_id FROM semantic_facts "
        "WHERE fact_text LIKE '%提到：%' ORDER BY updated_at DESC"
    ).fetchall()
    now = int(time.time() * 1000)
    report = {
        "total": len(rows),
        "last_24h": sum(1 for row in rows if row["updated_at"] >= now - DAY_MS),
        "last_1h": sum(1 for row in rows if row["updated_at"] >= now - DAY_MS // 24),
        "with_source_turn": sum(1 for row in rows if row["source_turn_id"]),
        "latest_ms": int(rows[0]["updated_at"]) if rows else 0,
    }
    args.out = args.out or ROOT / "eval" / "baselines" / "explicit-fact-2026-11-01.json"
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
