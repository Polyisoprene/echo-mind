"""SQLite implementation of ITurnTraceStore for per-turn execution timelines."""

from __future__ import annotations

import json
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import TurnRecord, TurnStep

INSERT_SQL = (
    "INSERT OR REPLACE INTO turn_traces "
    "(turn_id, chat_key, ts, trigger, status, rounds, sent_count, total_ms, model, "
    "context_count, trigger_count, system_prompt, user_prompt, steps_json) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
SELECT_SQL = (
    "SELECT turn_id, chat_key, ts, trigger, status, rounds, sent_count, "
    "total_ms, model, context_count, trigger_count, system_prompt, user_prompt, steps_json "
    "FROM turn_traces WHERE chat_key = ? ORDER BY ts DESC LIMIT ?"
)
SELECT_ALL_SQL = (
    "SELECT turn_id, chat_key, ts, trigger, status, rounds, sent_count, "
    "total_ms, model, context_count, trigger_count, system_prompt, user_prompt, steps_json "
    "FROM turn_traces ORDER BY ts DESC LIMIT ?"
)


def _steps_to_json(steps: tuple[TurnStep, ...]) -> str:
    return json.dumps([s.model_dump() for s in steps], ensure_ascii=False)


def _steps_from_json(raw: str) -> tuple[TurnStep, ...]:
    items: list[dict[str, Any]] = json.loads(raw or "[]")
    return tuple(TurnStep.model_validate(item) for item in items)


def _row_to_record(row: Any) -> TurnRecord:
    return TurnRecord(
        turn_id=str(row[0]),
        chat_key=str(row[1]),
        ts=int(row[2]),
        trigger=str(row[3]),
        status=str(row[4]),
        rounds=int(row[5]),
        sent_count=int(row[6]),
        total_ms=int(row[7]),
        model=str(row[8]),
        context_count=int(row[9] or 0),
        trigger_count=int(row[10] or 0),
        system_prompt=str(row[11] or ""),
        user_prompt=str(row[12] or ""),
        steps=_steps_from_json(str(row[13])),
    )


class SqliteTurnTraceStore:
    """Persist and read per-turn execution traces."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def save_turn(self, record: TurnRecord) -> None:
        """Insert or replace one turn trace."""
        params = (
            record.turn_id,
            record.chat_key,
            record.ts,
            record.trigger,
            record.status,
            record.rounds,
            record.sent_count,
            record.total_ms,
            record.model,
            record.context_count,
            record.trigger_count,
            record.system_prompt,
            record.user_prompt,
            _steps_to_json(record.steps),
        )
        async with self._db.connect() as conn:
            await conn.execute(INSERT_SQL, params)
            await conn.commit()

    async def list_turns(self, chat_key: str = "", limit: int = 40) -> tuple[TurnRecord, ...]:
        """Return the newest turns of one chat (or across all chats when chat_key is empty)."""
        clamped = max(1, min(limit, 200))
        async with self._db.connect() as conn:
            if not chat_key or chat_key == "all":
                cursor = await conn.execute(SELECT_ALL_SQL, (clamped,))
            else:
                cursor = await conn.execute(SELECT_SQL, (chat_key, clamped))
            rows = await cursor.fetchall()
        return tuple(_row_to_record(r) for r in rows)
