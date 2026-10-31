"""Read-only trait evidence projection for the inspector API."""

from __future__ import annotations

import json
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase


async def trait_evidence(
    db: SqliteDatabase, trait_id: int, limit: int = 20,
) -> list[dict[str, Any]]:
    async with db.connect() as conn:
        rows = await (await conn.execute(
            "SELECT id, quote, quote_kind, polarity, context_hash, memory_ids_json, "
            "created_ms FROM trait_evidence WHERE trait_id=? "
            "ORDER BY created_ms DESC, id DESC LIMIT ?",
            (trait_id, limit),
        )).fetchall()
    return [
        {
            "id": int(row[0]), "quote": str(row[1]), "quote_kind": str(row[2]),
            "polarity": int(row[3]), "context_hash": str(row[4]),
            "memory_ids": [int(item) for item in json.loads(row[5])],
            "created_ms": int(row[6]),
        }
        for row in rows
    ]
