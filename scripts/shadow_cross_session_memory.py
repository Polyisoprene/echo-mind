#!/usr/bin/env python
"""Read-only cross-session candidate scan; no live retrieval change."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from echomind.adapters.storage.memory_repo import FACT_COLUMNS
from echomind.adapters.storage.memory_rows import row_to_fact
from echomind.mind.session_memory_policy import RecallRequest, can_recall_across_sessions

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--chat-key", default="group:813506156")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "reports" / "cross_session_shadow.json"
    )
    args = parser.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        f"SELECT {FACT_COLUMNS} FROM semantic_facts "  # noqa: S608
        "WHERE sensitivity IN ('public','group') ORDER BY id DESC"
    ).fetchall()
    candidates = []
    for row in rows:
        fact = row_to_fact(row)
        if fact.chat_key == args.chat_key:
            continue
        if can_recall_across_sessions(RecallRequest(
            source_chat=fact.chat_key, current_chat=args.chat_key,
            sensitivity=fact.sensitivity, audience=fact.audience,
        )):
            candidates.append({
                "id": fact.fact_id, "source_chat": fact.chat_key,
                "subject": fact.subject, "text": fact.fact_text,
                "sensitivity": fact.sensitivity,
            })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {"chat_key": args.chat_key, "candidates": len(candidates)},
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
