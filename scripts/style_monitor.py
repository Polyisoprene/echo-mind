#!/usr/bin/env python
"""Report deterministic style metrics for recent self messages."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from echomind.mind.style_metrics import summarize

ROOT = Path(__file__).resolve().parents[1]


def _load(db: Path, since_ms: int, limit: int) -> list[str]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT text FROM chat_messages WHERE is_self=1 AND ts >= ? "
        "AND text != '' ORDER BY id DESC LIMIT ?", (since_ms, limit)
    ).fetchall()
    return [str(row[0]) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "style-monitor.json")
    args = parser.parse_args()

    now = int(time.time() * 1000)
    texts = _load(args.db, now - args.days * 86_400_000, args.limit)
    recent = _load(args.db, now - 86_400_000, 200)
    report = {
        "days": args.days,
        "overall": summarize(texts),
        "last_24h": summarize(recent),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
