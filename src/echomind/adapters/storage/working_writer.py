"""Versioned working-state writes (optimistic concurrency)."""

from __future__ import annotations

import json
import time

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.errors import WorkingStateConflict
from echomind.domain.models import WorkingSnapshot

UPSERT_SQL = (
    "INSERT INTO working_state (scope_key, valence, energy, jealousy, shyness, irritation, "
    "curiosity_drive, attachment_drive, jealousy_drive, social_drive, current_activity, "
    "inner_thought, intentions_json, curiosity_queue_json, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(scope_key) DO UPDATE SET valence=excluded.valence, "
    "energy=excluded.energy, jealousy=excluded.jealousy, shyness=excluded.shyness, "
    "irritation=excluded.irritation, curiosity_drive=excluded.curiosity_drive, "
    "attachment_drive=excluded.attachment_drive, jealousy_drive=excluded.jealousy_drive, "
    "social_drive=excluded.social_drive, current_activity=excluded.current_activity, "
    "inner_thought=excluded.inner_thought, intentions_json=excluded.intentions_json, "
    "curiosity_queue_json=excluded.curiosity_queue_json, updated_at=excluded.updated_at"
)
UPDATE_SQL = (
    "UPDATE working_state SET valence=?, energy=?, jealousy=?, shyness=?, irritation=?, "
    "curiosity_drive=?, attachment_drive=?, jealousy_drive=?, social_drive=?, "
    "current_activity=?, inner_thought=?, intentions_json=?, curiosity_queue_json=?, "
    "updated_at=? WHERE scope_key=? AND updated_at=?"
)


def _row(snapshot: WorkingSnapshot, now_ms: int) -> tuple[object, ...]:
    intents = json.dumps([i.model_dump() for i in snapshot.intentions], ensure_ascii=False)
    queue = json.dumps(list(snapshot.curiosity_queue), ensure_ascii=False)
    aff, drv = snapshot.affect, snapshot.drives
    return (
        snapshot.scope_key, aff.valence, aff.energy, aff.jealousy, aff.shyness,
        aff.irritation, drv.curiosity, drv.attachment, drv.jealousy_drive,
        drv.social_expression, snapshot.current_activity, snapshot.inner_thought,
        intents, queue, now_ms,
    )


async def _update(
    conn: object, row: tuple[object, ...], snapshot: WorkingSnapshot
) -> None:
    cursor = await conn.execute(  # type: ignore[attr-defined]
        UPDATE_SQL, (*row[1:], snapshot.scope_key, snapshot.revision)
    )
    if cursor.rowcount == 0:
        raise WorkingStateConflict(snapshot.scope_key)


async def save_snapshot(db: SqliteDatabase, snapshot: WorkingSnapshot) -> None:
    """Write once; a non-zero revision must still match or WorkingStateConflict is raised."""
    row = _row(snapshot, int(time.time() * 1000))
    async with db.connect() as conn:
        if snapshot.revision > 0:
            await _update(conn, row, snapshot)
        else:
            await conn.execute(UPSERT_SQL, row)
        await conn.commit()


__all__ = ["save_snapshot"]
