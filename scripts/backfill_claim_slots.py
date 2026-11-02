#!/usr/bin/env python
"""Dry-run/apply slot_key inference for existing claims; never supersedes."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path

from echomind.mind.claim_slots import infer_slot

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "claim_slots.json")
    args = parser.parse_args()
    if args.apply and os.getenv("CLAIM_SLOT_CONFIRM") != "yes":
        print(
            "REFUSED: slot inference has known false positives; "
            "set CLAIM_SLOT_CONFIRM=yes only after dry-run audit."
        )
        return 2
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, subject, value FROM claims WHERE slot_key='' AND status='asserted'"
    ).fetchall()
    matched: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for row in rows:
        slot = infer_slot(str(row["subject"]), str(row["value"]))
        if not slot:
            continue
        counts[slot] += 1
        matched.append({"id": int(row["id"]), "subject": str(row["subject"]),
                        "slot_key": slot, "value": str(row["value"])})
        if args.apply:
            con.execute("UPDATE claims SET slot_key=? WHERE id=?", (slot, int(row["id"])))
    if args.apply:
        con.commit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(matched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "scanned": len(rows),
                      "matched": len(matched), "slots": dict(counts)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
