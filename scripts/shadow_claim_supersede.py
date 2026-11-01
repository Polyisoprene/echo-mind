#!/usr/bin/env python
"""Read-only shadow scan: which asserted claims would be superseded."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from echomind.mind.claim_supersede import plan_supersedes
from echomind.mind.fact_shadow import ClaimView

ROOT = Path(__file__).resolve().parents[1]


def _view(row: sqlite3.Row) -> ClaimView:
    return ClaimView(
        subject=str(row["subject"]), value=str(row["value"]),
        predicate=str(row["predicate"]), belief=0.5,
        recorded_at_ms=int(row["recorded_at_ms"]), locked=False,
        chat_key=str(row["chat_key"]), scope=str(row["scope"]),
        owner_id=str(row["owner_id"]), sensitivity=str(row["sensitivity"]),
        audience=tuple(str(x) for x in json.loads(str(row["audience_json"] or "[]"))),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "reports" / "claim_supersede_shadow.json"
    )
    args = parser.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, chat_key, subject, predicate, value, recorded_at_ms, "
        "scope, owner_id, sensitivity, audience_json FROM claims "
        "WHERE status='asserted' ORDER BY recorded_at_ms DESC"
    ).fetchall()
    rows_by_key: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        rows_by_key[(str(row["chat_key"]), str(row["subject"]))].append(row)
    candidates: list[dict[str, Any]] = []
    for _key, group in rows_by_key.items():
        if len(group) < 2:
            continue
        new_row = group[0]
        new = _view(new_row)
        old_views = [_view(row) for row in group[1:]]
        old = plan_supersedes(new, old_views)
        if old:
            candidates.append({
                "chat_key": new.chat_key, "subject": new.subject,
                "predicate": new.predicate, "new_id": int(new_row["id"]),
                "new_value": new.value, "new_recorded": new.recorded_at_ms,
                "older": [
                    {"id": int(row["id"]), "value": str(row["value"]),
                     "recorded": int(row["recorded_at_ms"])}
                    for row, view in zip(group[1:], old_views, strict=True)
                    if view in old
                ],
            })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"groups": len(rows_by_key), "candidates": len(candidates)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
