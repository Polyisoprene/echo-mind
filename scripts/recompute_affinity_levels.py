#!/usr/bin/env python
"""Recompute social_bonds.affinity_level with the current thresholds.

Dry-run by default. `--apply` writes; run it during a deploy, not from the A line.
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.mind.memory_consolidator import compute_affinity_level  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    rows = list(conn.execute("SELECT chat_key, user_id, affinity_score, affinity_level FROM social_bonds"))
    changes = [(compute_affinity_level(float(score)), chat, uid, int(level))
               for chat, uid, score, level in rows]
    new_dist = Counter(new for new, *_ in changes)
    changed = sum(1 for new, _c, _u, old in changes if new != old)
    print(f"bonds={len(changes)} changed={changed} distribution={dict(sorted(new_dist.items()))}")
    for new, chat, uid, old in changes[:8]:
        print(f"  {chat} {uid}: Lv.{old} -> Lv.{new}")
    if args.apply and changed:
        conn.executemany(
            "UPDATE social_bonds SET affinity_level=? WHERE chat_key=? AND user_id=?",
            [(new, chat, uid) for new, chat, uid, _old in changes if new != _old],
        )
        conn.commit()
        print(f"applied: {changed} rows")
    elif changed:
        print("dry-run: pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
