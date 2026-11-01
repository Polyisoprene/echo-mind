#!/usr/bin/env python
"""Dry-run/apply shadow response attribution for historical chat messages."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from collections import Counter
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.interaction_outcome_repo import SqliteInteractionOutcomeStore
from echomind.core.config import load_config_from_json
from echomind.mind.response_attribution import ChatMessageRow, attribute_messages

ROOT = Path(__file__).resolve().parents[1]


def _summary(rows: tuple[object, ...], total_self: int) -> dict[str, object]:
    outcomes = [row for row in rows if hasattr(row, "attribution")]
    delays = sorted(float(row.delay_ms) for row in outcomes)
    n = len(delays)
    def pct(p: float) -> float:
        return round(delays[min(n - 1, int(p * (n - 1)))] / 1000, 1) if n else 0.0
    return {
        "self_messages": total_self,
        "outcomes": n,
        "coverage": round(n / max(1, total_self), 3),
        "attribution": dict(Counter(row.attribution for row in outcomes)),
        "delay_seconds": {"p50": pct(0.5), "p90": pct(0.9), "p95": pct(0.95)},
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--config", type=Path, default=ROOT / "data" / "config.json")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    cfg = load_config_from_json(args.config)
    aliases = tuple(dict.fromkeys((cfg.bot_name, *cfg.keywords)))
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    raw = con.execute(
        "SELECT id, chat_key, ts, is_self, sender_id, sender_name, text "
        "FROM chat_messages ORDER BY chat_key, ts, id"
    ).fetchall()
    messages = tuple(ChatMessageRow(
        message_id=int(row["id"]), chat_key=str(row["chat_key"]), ts=int(row["ts"]),
        is_self=bool(row["is_self"]), sender_id=str(row["sender_id"] or ""),
        sender_name=str(row["sender_name"] or ""), text=str(row["text"] or ""),
    ) for row in raw)
    outcomes = attribute_messages(messages, aliases)
    total_self = sum(1 for row in messages if row.is_self)
    report = _summary(tuple(outcomes), total_self)
    if args.apply:
        db = SqliteDatabase(args.db)
        await db.initialize()
        await SqliteInteractionOutcomeStore(db).save_many(outcomes)
        report["applied"] = len(outcomes)
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
