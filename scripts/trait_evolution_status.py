#!/usr/bin/env python
"""Read-only audit of real trait evidence, lifecycle, shadow and links."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _status(db: Path) -> dict[str, Any]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    traits = []
    for row in con.execute(
        "SELECT id, category, trait_text, status, evidence_count, contradiction_count "
        "FROM persona_traits ORDER BY id"
    ):
        evidence = list(con.execute(
            "SELECT context_hash, quote_kind, created_ms FROM trait_evidence "
            "WHERE trait_id=? ORDER BY id", (row["id"],),
        ))
        traits.append({
            "id": row["id"], "category": row["category"],
            "text": row["trait_text"], "status": row["status"],
            "cached_evidence": row["evidence_count"],
            "ledger_rows": len(evidence),
            "distinct_contexts": len({item["context_hash"] for item in evidence}),
            "quote_kinds": sorted({item["quote_kind"] for item in evidence}),
            "last_evidence_ms": max(
                (item["created_ms"] for item in evidence), default=0
            ),
        })
    shadow = list(con.execute(
        "SELECT trait_ids_json, allowed_tools_json, actual_tools_json, allow_refusal "
        "FROM trait_action_shadow"
    ))
    return {
        "db": str(db),
        "traits": traits,
        "shadow": {
            "rows": len(shadow),
            "nonempty_trait_rows": sum(bool(json.loads(r["trait_ids_json"])) for r in shadow),
            "allowed_tools": sorted({
                tool for r in shadow for tool in json.loads(r["allowed_tools_json"])
            }),
            "actual_tools": sorted({
                tool for r in shadow for tool in json.loads(r["actual_tools_json"])
            }),
            "refusal_rows": sum(bool(r["allow_refusal"]) for r in shadow),
        },
        "links": con.execute("SELECT COUNT(*) FROM trait_memory_links").fetchone()[0],
        "candidates": dict(con.execute(
            "SELECT status, COUNT(*) FROM trait_candidates GROUP BY status"
        ).fetchall()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, action="append")
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "eval" / "baselines" / "trait-live-status-2026-11-01.json",
    )
    args = parser.parse_args()
    dbs = args.db or [ROOT / "data" / "echomind.db", ROOT / "data-xiaomo" / "echomind.db"]
    report = [_status(path) for path in dbs]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
