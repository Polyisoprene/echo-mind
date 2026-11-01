#!/usr/bin/env python
"""Print the evidence-bound narrative projection (read-only)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.mind.narrative_identity import build_narrative

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    await db.initialize()
    narrative = await build_narrative(
        SqliteWorkingStateStore(db), SqliteTraitEvidenceStore(db),
    )
    payload = {"trait_ids": narrative.trait_ids, "lines": narrative.lines}
    if args.out:
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
