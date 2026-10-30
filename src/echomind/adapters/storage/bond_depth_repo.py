"""SQLite adapter persisting per-member interaction counters for earned bond depth."""

from __future__ import annotations

import time

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.ports import IBondDepthStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bond_depth_stats (
    chat_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    msgs INTEGER NOT NULL DEFAULT 0,
    her_msgs INTEGER NOT NULL DEFAULT 0,
    replies_to_them INTEGER NOT NULL DEFAULT 0,
    responded_to_her INTEGER NOT NULL DEFAULT 0,
    sessions INTEGER NOT NULL DEFAULT 0,
    impact_sum REAL NOT NULL DEFAULT 0.0,
    impact_n INTEGER NOT NULL DEFAULT 0,
    betrayals INTEGER NOT NULL DEFAULT 0,
    updated_ms INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_key, user_id)
);
"""

_COLUMNS = (
    "chat_key, user_id, msgs, her_msgs, replies_to_them, responded_to_her, "
    "sessions, impact_sum, impact_n, betrayals, updated_ms"
)
_UPSERT_SQL = """
INSERT INTO bond_depth_stats (
    chat_key, user_id, msgs, her_msgs, replies_to_them, responded_to_her,
    sessions, impact_sum, impact_n, betrayals, updated_ms
) VALUES (?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(chat_key, user_id) DO UPDATE SET
    msgs=excluded.msgs, her_msgs=excluded.her_msgs,
    replies_to_them=excluded.replies_to_them,
    responded_to_her=excluded.responded_to_her, sessions=excluded.sessions,
    impact_sum=excluded.impact_sum, impact_n=excluded.impact_n,
    betrayals=excluded.betrayals, updated_ms=excluded.updated_ms
"""
_GET_SQL = """
SELECT chat_key, user_id, msgs, her_msgs, replies_to_them, responded_to_her,
       sessions, impact_sum, impact_n, betrayals, updated_ms
FROM bond_depth_stats WHERE chat_key=? AND user_id=?
"""
_TOP_SQL = """
SELECT chat_key, user_id, msgs, her_msgs, replies_to_them, responded_to_her,
       sessions, impact_sum, impact_n, betrayals, updated_ms
FROM bond_depth_stats ORDER BY msgs DESC LIMIT ?
"""


def _row_to_stats(row: aiosqlite.Row) -> BondDepthStats:
    return BondDepthStats(
        chat_key=str(row[0]), user_id=str(row[1]),
        msgs=int(row[2]), her_msgs=int(row[3]), replies_to_them=int(row[4]),
        responded_to_her=int(row[5]), sessions=int(row[6]),
        impact_sum=float(row[7]), impact_n=int(row[8]), betrayals=int(row[9]),
        updated_ms=int(row[10]),
    )


class SqliteBondDepthStore(IBondDepthStore):
    """Persist absolute counters plus incremental affect/betrayal observations."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def ensure_schema(self) -> None:
        async with self._db.connect() as conn:
            await conn.executescript(_SCHEMA)
            await conn.commit()

    async def upsert_stats(self, stats: BondDepthStats) -> None:
        payload = (
            stats.chat_key, stats.user_id, stats.msgs, stats.her_msgs,
            stats.replies_to_them, stats.responded_to_her, stats.sessions,
            stats.impact_sum, stats.impact_n, stats.betrayals,
            stats.updated_ms or int(time.time() * 1000),
        )
        async with self._db.connect() as conn:
            await conn.execute(_UPSERT_SQL, payload)
            await conn.commit()

    async def add_impact(
        self, chat_key: str, user_id: str, magnitude: float, *, betray: bool = False
    ) -> None:
        now_ms = int(time.time() * 1000)
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT INTO bond_depth_stats (chat_key, user_id, impact_sum, impact_n, "
                "betrayals, updated_ms) VALUES (?, ?, ?, 1, ?, ?) "
                "ON CONFLICT(chat_key, user_id) DO UPDATE SET "
                "impact_sum=bond_depth_stats.impact_sum+excluded.impact_sum, "
                "impact_n=bond_depth_stats.impact_n+1, "
                "betrayals=bond_depth_stats.betrayals+excluded.betrayals, "
                "updated_ms=excluded.updated_ms",
                (chat_key, user_id, abs(magnitude), int(betray), now_ms),
            )
            await conn.commit()

    async def get_stats(self, chat_key: str, user_id: str) -> BondDepthStats | None:
        async with self._db.connect() as conn:
            cursor = await conn.execute(_GET_SQL, (chat_key, user_id))
            row = await cursor.fetchone()
        return _row_to_stats(row) if row else None

    async def top_stats(self, limit: int = 50) -> tuple[BondDepthStats, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(_TOP_SQL, (limit,))
            rows = await cursor.fetchall()
        return tuple(_row_to_stats(r) for r in rows)
