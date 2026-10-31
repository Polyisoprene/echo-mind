#!/usr/bin/env python
"""Report trait evolution health without guessing or waiting on a clock."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.mind.trait_health import TraitHealth

ROOT = Path(__file__).resolve().parents[1]


def status(db_path: Path) -> TraitHealth:
    import sqlite3

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    active = con.execute(
        "SELECT COUNT(*), COALESCE(MAX(active_since_ms), 0) FROM persona_traits "
        "WHERE status='active'"
    ).fetchone()
    active_count, active_since = int(active[0]), int(active[1])
    shadow = con.execute(
        "SELECT COUNT(*) FROM trait_action_shadow WHERE created_ms >= ?",
        (active_since,),
    ).fetchone()[0]
    nonempty = con.execute(
        "SELECT COUNT(*) FROM trait_action_shadow WHERE created_ms >= ? "
        "AND trait_ids_json != '[]'", (active_since,),
    ).fetchone()[0]
    links = con.execute("SELECT COUNT(*) FROM trait_memory_links").fetchone()[0]
    latest = con.execute("SELECT COALESCE(MAX(ts),0) FROM turn_traces").fetchone()[0]
    return TraitHealth(active_count, int(shadow), int(nonempty), int(links), int(latest))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    db = SqliteDatabase(args.db)
    # initialize is safe/idempotent and ensures schema exists on a fresh DB.
    import asyncio
    asyncio.run(db.initialize())
    health = status(args.db)
    print(json.dumps({
        "status": health.status, "active_traits": health.active_traits,
        "shadow_since_activation": health.shadow_since_activation,
        "nonempty_shadow": health.nonempty_shadow,
        "causal_links": health.causal_links,
        "latest_turn_ms": health.latest_turn_ms,
    }, ensure_ascii=False, indent=2))
    if args.check and health.status == "shadow_missing_trait":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
