#!/usr/bin/env python
"""List or correct cue-raised sensitivity (D7)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.storage.database import SqliteDatabase  # noqa: E402
from echomind.adapters.storage.sensitivity_repo import SqliteSensitivityReviewer  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--kind", choices=("semantic", "episodic"), default="semantic")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--id", type=int)
    parser.add_argument("--set", choices=("public", "group", "private", "secret"))
    parser.add_argument("--reviewer", default="operator")
    parser.add_argument("--reason", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SqliteDatabase(args.db)
    await db.initialize()
    reviewer = SqliteSensitivityReviewer(db)
    if args.list or args.id is None:
        for row in await reviewer.list_non_group(args.kind):
            print(row)
        return 0
    if args.set is None:
        print("--set is required when --id is given")
        return 2
    if not args.apply:
        print("dry-run: pass --apply to write")
        return 0
    previous = await reviewer.apply(
        memory_kind=args.kind, memory_id=args.id, to_sensitivity=args.set,
        reviewer=args.reviewer, reason=args.reason,
    )
    print(f"{args.id}: {previous} -> {args.set}" if previous else "not found")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
