"""SQLite implementation of ISkillConfigStore for per-skill settings."""

from __future__ import annotations

import time

from echomind.adapters.storage.database import SqliteDatabase

SELECT_SQL = "SELECT key, value FROM skill_configs WHERE skill = ?"
UPSERT_SQL = (
    "INSERT INTO skill_configs (skill, key, value, updated_at) VALUES (?, ?, ?, ?) "
    "ON CONFLICT(skill, key) DO UPDATE SET value = excluded.value, "
    "updated_at = excluded.updated_at"
)


class SqliteSkillConfigStore:
    """Persist per-skill configuration values."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def get_skill_config(self, skill: str) -> dict[str, str]:
        """Return all stored values of one skill."""
        async with self._db.connect() as conn:
            cursor = await conn.execute(SELECT_SQL, (skill,))
            rows = await cursor.fetchall()
        return {str(r[0]): str(r[1]) for r in rows}

    async def set_skill_config(self, skill: str, values: dict[str, str]) -> None:
        """Upsert the provided keys; empty strings are stored as-is (explicit clear)."""
        if not values:
            return
        now_ms = int(time.time() * 1000)
        async with self._db.connect() as conn:
            for key, value in values.items():
                await conn.execute(UPSERT_SQL, (skill, key, value, now_ms))
            await conn.commit()
