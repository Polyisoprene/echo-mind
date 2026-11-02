"""Persist BDI intentions as durable events whenever working state is saved."""

from __future__ import annotations

import time

from aiosqlite import Connection

from echomind.domain.models import WorkingSnapshot


async def sync_intention_events(conn: Connection, snapshot: WorkingSnapshot) -> None:
    now = int(time.time() * 1000)
    active: set[tuple[str, str, str]] = set()
    for item in snapshot.intentions:
        source = item.source_chat_key or snapshot.scope_key
        active.add((source, item.summary, item.target_chat_key))
        await conn.execute(
            "INSERT INTO intention_events "
            "(source_chat_key, target_chat_key, summary, status, created_at_ms, updated_at_ms) "
            "VALUES (?,?,?,'open',?,?) "
            "ON CONFLICT(source_chat_key, summary, target_chat_key) DO UPDATE SET "
            "updated_at_ms=excluded.updated_at_ms",
            (
                source, item.target_chat_key, item.summary,
                item.created_at_ms or now, now,
            ),
        )
    rows = await (await conn.execute(
        "SELECT id, source_chat_key, summary, target_chat_key FROM intention_events "
        "WHERE status='open'"
    )).fetchall()
    for event_id, source, summary, target in rows:
        if (str(source), str(summary), str(target)) not in active:
            await conn.execute(
                "UPDATE intention_events SET status='closed', updated_at_ms=? WHERE id=?",
                (now, int(event_id)),
            )
