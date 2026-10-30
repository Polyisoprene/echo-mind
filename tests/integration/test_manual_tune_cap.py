"""Stage 30 S30-7: console tuning is clipped and capped like any other personality change."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.mind.persona_dynamics import DAILY_CAP, capped_manual_delta


async def test_manual_delta_is_clipped_and_capped(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "m.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    await store.ensure_default_params()

    applied, remaining = await capped_manual_delta(store, "persona_warmth", 50.0)
    assert applied == 2.0, "one console edit must not exceed the per-turn clip"
    assert remaining == DAILY_CAP - 2.0

    for _ in range(10):
        await store.update_plastic_param("persona_warmth", 2.0, "spend budget", reward=0.0)
    applied, remaining = await capped_manual_delta(store, "persona_warmth", 5.0)
    assert abs(applied) <= 2.0
    assert remaining >= 0.0
