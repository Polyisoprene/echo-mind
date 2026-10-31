#!/usr/bin/env python
"""Delete disclosure rows older than N days (D18)."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.storage.database import SqliteDatabase  # noqa: E402
from echomind.adapters.storage.disclosure_repo import SqliteDisclosureLog  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--days", type=float, default=30.0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SqliteDatabase(args.db)
    await db.initialize()
    cutoff = int((time.time() - args.days * 86400) * 1000)
    async with db.connect() as conn:
        count = await (await conn.execute(
            "SELECT COUNT(*) FROM disclosures WHERE ts_ms < ?", (cutoff,)
        )).fetchone()
    print(f"cutoff_ms={cutoff} older_rows={int(count[0]) if count else 0}")
    if args.apply:
        deleted = await SqliteDisclosureLog(db).prune(cutoff)
        print(f"deleted={deleted}")
    else:
        print("dry-run: pass --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
