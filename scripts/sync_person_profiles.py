#!/usr/bin/env python
"""Build and persist person-level profiles (persons / person_bonds / bond_venues)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.storage.database import SqliteDatabase  # noqa: E402
from echomind.adapters.storage.person_level_repo import load_bonds, load_stats  # noqa: E402
from echomind.adapters.storage.person_store import SqlitePersonStore  # noqa: E402
from echomind.mind.person_level import build_profiles  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SqliteDatabase(args.db)
    await db.initialize()
    bonds, stats = await load_bonds(db), await load_stats(db)
    profiles = build_profiles(bonds, stats)
    print(f"profiles={len(profiles)} bonds={len(bonds)} stats={len(stats)}")
    if args.apply:
        store = SqlitePersonStore(db)
        await store.save(profiles, bonds)
        print("applied")
    else:
        print("dry-run: pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
