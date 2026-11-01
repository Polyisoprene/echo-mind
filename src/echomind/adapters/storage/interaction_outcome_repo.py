"""Persistence for shadow response-attribution outcomes."""

from __future__ import annotations

from typing import Any, cast

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.interaction_outcome import InteractionOutcome


def _row(row: aiosqlite.Row) -> InteractionOutcome:
    return InteractionOutcome(
        self_message_id=int(row[0]), response_message_id=int(row[1]),
        chat_key=str(row[2]), self_ts=int(row[3]), response_ts=int(row[4]),
        delay_ms=int(row[5]), attribution=cast(Any, str(row[6])),
        sender_id=str(row[7]), sender_name=str(row[8]),
        response_text=str(row[9]), created_ms=int(row[10]),
    )


class SqliteInteractionOutcomeStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def save_many(self, rows: tuple[InteractionOutcome, ...]) -> int:
        async with self._db.connect() as conn:
            for row in rows:
                await conn.execute(
                    "INSERT OR IGNORE INTO interaction_outcomes "
                    "(self_message_id, response_message_id, chat_key, self_ts, "
                    "response_ts, delay_ms, attribution, sender_id, sender_name, "
                    "response_text, created_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (row.self_message_id, row.response_message_id, row.chat_key,
                     row.self_ts, row.response_ts, row.delay_ms, row.attribution,
                     row.sender_id, row.sender_name, row.response_text, row.created_ms),
                )
            await conn.commit()
            return len(rows)

    async def list_for_chat(
        self, chat_key: str, limit: int = 200,
    ) -> tuple[InteractionOutcome, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT self_message_id, response_message_id, chat_key, self_ts, "
                "response_ts, delay_ms, attribution, sender_id, sender_name, "
                "response_text, created_ms FROM interaction_outcomes "
                "WHERE chat_key=? ORDER BY self_ts DESC LIMIT ?",
                (chat_key, limit),
            )
            return tuple(_row(row) for row in await cursor.fetchall())
