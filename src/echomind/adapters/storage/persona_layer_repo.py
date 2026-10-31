"""SQLite store for the fast persona state and the pending daily observations.

Two tables:
  * `persona_state`   one row per dimension: the current offset and when it was set;
  * `persona_pending` one row per (dimension, day): observations awaiting settlement.

Settlement pops whole days strictly before "today", so a day is never settled twice
and the calendar-day budget cannot be bypassed by a rolling window.
"""

from __future__ import annotations

import datetime
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase

CST = datetime.timezone(datetime.timedelta(hours=8))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS persona_state (
    key TEXT PRIMARY KEY,
    offset REAL NOT NULL DEFAULT 0.0,
    updated_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS persona_pending (
    key TEXT NOT NULL,
    day TEXT NOT NULL,
    total REAL NOT NULL DEFAULT 0.0,
    n INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, day)
);
CREATE TABLE IF NOT EXISTS persona_settlement (
    key TEXT PRIMARY KEY,
    settled_ms INTEGER NOT NULL DEFAULT 0
);
"""


def _day(now_ms: int) -> str:
    return datetime.datetime.fromtimestamp(now_ms / 1000.0, tz=CST).date().isoformat()


class SqlitePersonaLayerStore:
    """Persist the fast offset and the daily evidence buffer for the persona layers."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    @classmethod
    async def open(cls, db: SqliteDatabase) -> SqlitePersonaLayerStore:
        """Build the store and create its tables in one step."""
        store = cls(db)
        await store.ensure_schema()
        return store

    async def ensure_schema(self) -> None:
        async with self._db.connect() as conn:
            await conn.executescript(_SCHEMA)
            await conn.commit()

    async def load_state(self) -> dict[str, tuple[float, int]]:
        async with self._db.connect() as conn:
            cursor = await conn.execute("SELECT key, offset, updated_ms FROM persona_state")
            rows = await cursor.fetchall()
        return {str(r[0]): (float(r[1]), int(r[2])) for r in rows}

    async def save_state(self, key: str, offset: float, now_ms: int) -> None:
        sql = (
            "INSERT INTO persona_state (key, offset, updated_ms) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET offset=excluded.offset, "
            "updated_ms=excluded.updated_ms"
        )
        async with self._db.connect() as conn:
            await conn.execute(sql, (key, offset, now_ms))
            await conn.commit()

    async def record_observation(self, key: str, delta: float, now_ms: int) -> None:
        """Accumulate one turn's observation into today's pending bucket."""
        sql = (
            "INSERT INTO persona_pending (key, day, total, n) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(key, day) DO UPDATE SET total=persona_pending.total + excluded.total, "
            "n=persona_pending.n + 1"
        )
        async with self._db.connect() as conn:
            await conn.execute(sql, (key, _day(now_ms), delta))
            await conn.commit()

    async def pop_observations(self, now_ms: int) -> dict[str, tuple[float, int]]:
        """Return {key: (total, last_settled_ms)} for days before today, then settle them."""
        today = _day(now_ms)
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT p.key, SUM(p.total), COALESCE(s.settled_ms, 0) "
                "FROM persona_pending p LEFT JOIN persona_settlement s ON s.key = p.key "
                "WHERE p.day < ? GROUP BY p.key",
                (today,),
            )
            rows: list[Any] = list(await cursor.fetchall())
            await conn.execute("DELETE FROM persona_pending WHERE day < ?", (today,))
            for row in rows:
                await conn.execute(
                    "INSERT INTO persona_settlement (key, settled_ms) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET settled_ms=excluded.settled_ms",
                    (str(row[0]), now_ms),
                )
            await conn.commit()
        return {str(r[0]): (float(r[1]), int(r[2])) for r in rows if r[1] is not None}
