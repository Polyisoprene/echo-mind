"""P3: disclosure decisions are auditable and 'who knows' is persisted."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from echomind.adapters.storage.disclosure_repo import SqliteDisclosureLog
from echomind.core.bootstrap import EchoMindContainer


@pytest.mark.asyncio
async def test_disclosure_log_and_knowledge(tmp_path: Path) -> None:
    db_path = tmp_path / "log.db"
    container = await EchoMindContainer.create(db_path=db_path)
    log = SqliteDisclosureLog(container.db)

    await log.log_disclosure(
        memory_kind="semantic", memory_id=7, venue="group:1",
        audience=("L",), action="keep", reason="owner_absent",
    )
    await log.mark_known("semantic", 7, "L", "told_by_me")
    await log.mark_known("semantic", 7, "M", "overheard", 0.6)

    assert await log.who_knows("semantic", 7) == (("L", "told_by_me"), ("M", "overheard"))

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT venue, action, reason, phase FROM disclosures WHERE memory_id=7"
    ).fetchone()
    assert row == ("group:1", "keep", "owner_absent", "gate")
