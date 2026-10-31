#!/usr/bin/env python
"""Link active trait evidence to memories whose source_quote matches exactly."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_quote_lookup import SqliteMemoryQuoteLookup
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.mind.trait_memory_linker import link_exact_quotes

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--trait-id", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SqliteDatabase(args.db)
    await db.initialize()
    query = (
        "SELECT id, chat_key FROM persona_traits WHERE status='active' AND id=?"
        if args.trait_id else
        "SELECT id, chat_key FROM persona_traits WHERE status='active'"
    )
    params = (args.trait_id,) if args.trait_id else ()
    async with db.connect() as conn:
        rows = list(await (await conn.execute(query, params)).fetchall())
    if not rows:
        print("no active traits")
        return 0

    evidence_store = SqliteTraitEvidenceStore(db)
    lookup = SqliteMemoryQuoteLookup(db)
    links = SqliteTraitMemoryLinkStore(db)
    for trait_id, chat_key in rows:
        evidence = await evidence_store.list_trait_evidence(int(trait_id), 200)
        result = await link_exact_quotes(
            int(trait_id), str(chat_key), evidence, lookup, links,
            dry_run=args.dry_run,
        )
        print(f"{trait_id} semantic={result.semantic} episodic={result.episodic} "
              f"skipped={result.skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
