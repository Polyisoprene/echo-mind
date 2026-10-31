#!/usr/bin/env python
"""Create an explicit disclosure grant for a secret memory (D5)."""

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
    parser.add_argument("--kind", choices=("semantic", "episodic"), default="semantic")
    parser.add_argument("--memory-id", type=int, required=True)
    parser.add_argument("--grantee", required=True)
    parser.add_argument("--by", required=True)
    parser.add_argument("--expires-days", type=float, default=0.0)
    args = parser.parse_args()

    db = SqliteDatabase(args.db)
    await db.initialize()
    expires = int((time.time() + args.expires_days * 86400) * 1000) if args.expires_days else None
    await SqliteDisclosureLog(db).grant(
        memory_kind=args.kind, memory_id=args.memory_id, grantee_id=args.grantee,
        granted_by=args.by, expires_ms=expires,
    )
    print(f"granted {args.kind}#{args.memory_id} to {args.grantee} by {args.by}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
