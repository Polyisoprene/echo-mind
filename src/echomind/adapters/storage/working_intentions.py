"""Persist BDI intentions as durable events whenever working state is saved."""

from __future__ import annotations

import time

from aiosqlite import Connection

from echomind.domain.models import WorkingSnapshot


async def sync_intention_events(conn: Connection, snapshot: WorkingSnapshot) -> None:
    now = int(time.time() * 1000)
    for item in snapshot.intentions:
        await conn.execute(
            "INSERT INTO intention_events "
            "(source_chat_key, target_chat_key, summary, status, created_at_ms, updated_at_ms) "
            "VALUES (?,?,?,'open',?,?) "
            "ON CONFLICT(source_chat_key, summary, target_chat_key) DO UPDATE SET "
            "updated_at_ms=excluded.updated_at_ms",
            (
                item.source_chat_key or snapshot.scope_key,
                item.target_chat_key, item.summary,
                item.created_at_ms or now, now,
            ),
        )
