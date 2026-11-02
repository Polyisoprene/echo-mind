"""Durable BDI intention events and delivery binding."""

from __future__ import annotations

from typing import Any

from echomind.adapters.storage.database import SqliteDatabase


async def _bind_rows(
    conn: Any, rows: Any, joined: str, message_ids: tuple[str, ...],
    target_chat_key: str,
) -> int:
    updated = 0
    for event_id, summary in rows:
        root = str(summary)[:4]
        if not root or root not in joined:
            continue
        await conn.execute(
            "UPDATE intention_events SET status='fulfilled', "
            "message_id=?, target_chat_key=?, updated_at_ms=strftime('%s','now')*1000 "
            "WHERE id=? AND status='open'",
            (message_ids[0] if message_ids else "", target_chat_key, int(event_id)),
        )
        updated += 1
    return updated


class IntentionEventStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def mark_delivered(
        self, source_chat_key: str, target_chat_key: str,
        sent_texts: tuple[str, ...], message_ids: tuple[str, ...],
    ) -> int:
        """Bind successful sends to matching open events; returns rows updated."""
        joined = " ".join(sent_texts)
        updated = 0
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id, summary FROM intention_events "
                "WHERE source_chat_key=? AND (target_chat_key=? OR target_chat_key='') "
                "AND status='open' ORDER BY updated_at_ms DESC",
                (source_chat_key, target_chat_key),
            )
            rows = list(await cursor.fetchall())
            updated = await _bind_rows(conn, rows, joined, message_ids, target_chat_key)
            if not updated and rows:
                await conn.execute(
                    "UPDATE intention_events SET status='fulfilled', "
                    "message_id=?, target_chat_key=?, updated_at_ms=strftime('%s','now')*1000 "
                    "WHERE id=? AND status='open'",
                    (message_ids[0] if message_ids else "", target_chat_key, int(rows[0][0])),
                )
                updated = 1
            await conn.commit()
        return updated
