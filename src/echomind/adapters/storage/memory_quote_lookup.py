"""Exact source_quote lookup for auditable trait-memory links."""

from __future__ import annotations

from echomind.adapters.storage.database import SqliteDatabase


class SqliteMemoryQuoteLookup:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def semantic_ids(self, chat_key: str, quote: str) -> tuple[int, ...]:
        return await self._ids("semantic_facts", chat_key, quote)

    async def episodic_ids(self, chat_key: str, quote: str) -> tuple[int, ...]:
        return await self._ids("episodic_memories", chat_key, quote)

    async def _ids(self, table: str, chat_key: str, quote: str) -> tuple[int, ...]:
        if not quote:
            return ()
        # Table name is a fixed internal literal, never user input.
        sql = f"SELECT id FROM {table} WHERE chat_key=? AND source_quote=? ORDER BY id"  # noqa: S608
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key, quote))
            return tuple(int(row[0]) for row in await cursor.fetchall())
