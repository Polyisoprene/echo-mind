#!/usr/bin/env python
"""Audit chat_key='global' facts (D6); apply marks public web snippets."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.storage.database import SqliteDatabase  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SqliteDatabase(args.db)
    await db.initialize()
    async with db.connect() as conn:
        rows = await (await conn.execute(
            "SELECT id, subject, owner_id, source_person_id, sensitivity "
            "FROM semantic_facts WHERE chat_key='global' ORDER BY id"
        )).fetchall()
        personal = [r for r in rows if r[2] or r[3]]
        print(f"global={len(rows)} with_owner_or_source={len(personal)}")
        for r in personal:
            print(f"  PERSONAL #{r[0]} {r[1]}")
        if args.apply:
            await conn.execute(
                "UPDATE semantic_facts SET sensitivity='public' "
                "WHERE chat_key='global' AND owner_id='' AND source_person_id=''"
            )
            await conn.commit()
            print("applied: global web snippets -> public")
        else:
            print("dry-run: pass --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
