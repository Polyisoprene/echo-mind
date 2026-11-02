"""BDI intentions are durable events, not only working-state JSON."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.working_writer import save_snapshot
from echomind.domain.models import IntentionItem, WorkingSnapshot


@pytest.mark.asyncio
async def test_save_snapshot_persists_open_intention(tmp_path: Path) -> None:
    db_path = tmp_path / "intention.db"
    await SqliteDatabase(db_path).initialize()
    snapshot = WorkingSnapshot(
        scope_key="global",
        intentions=(IntentionItem(
            summary="去群里说", created_at_ms=1, expires_at_ms=0,
            target_chat_key="group:1", source_chat_key="private:1",
        ),),
    )
    await save_snapshot(SqliteDatabase(db_path), snapshot)
    await save_snapshot(SqliteDatabase(db_path), snapshot)
    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT source_chat_key,target_chat_key,summary,status FROM intention_events"
    ).fetchall()
    assert rows == [("private:1", "group:1", "去群里说", "open")]
    await save_snapshot(SqliteDatabase(db_path), WorkingSnapshot(scope_key="global"))
    status = con.execute("SELECT status FROM intention_events").fetchone()[0]
    assert status == "closed"
