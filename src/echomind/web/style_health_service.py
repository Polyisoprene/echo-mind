"""Read-only deterministic style projection for the inspector API."""

from __future__ import annotations

import time
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.mind.style_metrics import summarize


async def style_health(db: SqliteDatabase, chat_key: str = "") -> dict[str, Any]:
    since = int(time.time() * 1000) - 86_400_000
    sql = (
        "SELECT text FROM chat_messages WHERE is_self=1 AND ts>=? AND text!=''"  # noqa: S608
        + (" AND chat_key=?" if chat_key else "")
        + " ORDER BY id DESC LIMIT 500"
    )
    async with db.connect() as conn:
        rows = await (await conn.execute(
            sql, (since, chat_key) if chat_key else (since,)
        )).fetchall()
    texts = [str(row[0]) for row in rows]
    return {"window": "24h", "chat_key": chat_key or "all", **summarize(texts)}
