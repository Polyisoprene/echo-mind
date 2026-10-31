#!/usr/bin/env python
"""Report live trait evidence and how many traits survive a min-evidence filter."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'echomind.db'}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT trait_text, strength, evidence_count, contradiction_count, chat_key "
        "FROM persona_traits ORDER BY evidence_count DESC, strength DESC"
    ).fetchall()
    print(f"traits={len(rows)}")
    for threshold in (1, 2, 3):
        print(f"  evidence>={threshold}: {sum(r[2] >= threshold for r in rows)}")
    for text, strength, evidence, contradiction, chat in rows:
        print(f"  [{chat or 'global'}] evidence={evidence} contra={contradiction} "
              f"strength={strength} {text[:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
