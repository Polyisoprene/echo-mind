"""P0: interaction outcomes persist idempotently."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.interaction_outcome_repo import SqliteInteractionOutcomeStore
from echomind.domain.interaction_outcome import InteractionOutcome


async def test_outcome_roundtrip_and_dedupe(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "outcomes.db")
    await db.initialize()
    row = InteractionOutcome(
        self_message_id=1, response_message_id=2, chat_key="g",
        self_ts=10, response_ts=20, delay_ms=10, attribution="mention",
        sender_id="u", sender_name="u", response_text="回音", created_ms=20,
    )
    store = SqliteInteractionOutcomeStore(db)
    await store.save_many((row,))
    await store.save_many((row,))
    rows = await store.list_for_chat("g")
    assert len(rows) == 1
    assert rows[0].attribution == "mention"
    assert rows[0].delay_ms == 10
