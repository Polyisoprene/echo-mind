#!/usr/bin/env python
"""Compare current all-traits prompt with an active-only prompt (no live edit)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import PersonaTrait
from echomind.mind.personality import synthesize_live_persona_directive

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    await db.initialize()
    working = SqliteWorkingStateStore(db)
    params = await working.get_plastic_params()
    traits = await working.sync_persona_traits()
    async with db.connect() as conn:
        rows = await (await conn.execute(
            "SELECT id, category, trait_text, strength, evidence_count, contradiction_count "
            "FROM persona_traits WHERE status='active' ORDER BY id"
        )).fetchall()
    active = tuple(
        PersonaTrait(
            trait_id=int(row[0]), category=row[1], trait_text=str(row[2]),
            strength=int(row[3]), evidence_count=int(row[4]),
            contradiction_count=int(row[5]),
        )
        for row in rows
    )
    current = synthesize_live_persona_directive(params, traits)
    active_only = synthesize_live_persona_directive(params, active)
    report = {
        "db": str(args.db),
        "all_traits": len(traits),
        "active_traits": len(active),
        "current_len": len(current),
        "active_only_len": len(active_only),
        "delta": len(active_only) - len(current),
        "removed_traits": [
            trait.trait_text for trait in traits
            if trait.trait_id not in {item.trait_id for item in active}
        ],
    }
    args.out = args.out or (
        ROOT / "eval" / "baselines" / "persona-active-prompt-impact-2026-11-01.json"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
