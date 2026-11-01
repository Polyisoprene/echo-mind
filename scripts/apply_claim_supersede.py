#!/usr/bin/env python
"""Dry-run/apply the conservative claim supersede plan."""

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


def _candidate(group: list[sqlite3.Row]) -> dict[str, Any] | None:
    if len(group) < 2:
        return None
    new = _view(group[0])
    old_views = [_view(row) for row in group[1:]]
    old = plan_supersedes(new, old_views)
    if not old:
        return None
    return {
        "new_id": int(group[0]["id"]), "subject": new.subject,
        "new_value": new.value,
        "old": [{"id": int(row["id"]), "value": str(row["value"])}
                for row, view in zip(group[1:], old_views, strict=True)
                if view in old],
    }


def _apply(con: sqlite3.Connection, record: dict[str, Any]) -> None:
    for item in record["old"]:
        con.execute(
            "UPDATE claims SET status='superseded', valid_to_ms=?, "
            "superseded_by=? WHERE id=? AND status='asserted'",
            (record["new_recorded"], record["new_id"], item["id"]),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "reports" / "claim_supersede_apply.json"
    )
    args = parser.parse_args()
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, chat_key, subject, predicate, value, recorded_at_ms, "
        "scope, owner_id, sensitivity, audience_json FROM claims "
        "WHERE status='asserted' ORDER BY recorded_at_ms DESC"
    ).fetchall()
    groups: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        groups[(str(row["chat_key"]), str(row["subject"]))].append(row)
    applied: list[dict[str, Any]] = []
    for _key, group in groups.items():
        record = _candidate(group)
        if record is None:
            continue
        record["new_recorded"] = int(group[0]["recorded_at_ms"])
        if args.apply:
            _apply(con, record)
            con.commit()
        applied.append(record)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(applied, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "groups": len(applied)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
