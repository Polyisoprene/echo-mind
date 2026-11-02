"""SQLite FTS5 lexical index; shadow-only until recall parity is measured."""

from __future__ import annotations

import re

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import SemanticFact


def _chunk_terms(chunk: str) -> list[str]:
    if chunk.isascii():
        return [chunk] if len(chunk) >= 3 else []
    return [chunk[i:i + 3] for i in range(0, max(1, len(chunk) - 2))]


def _query_terms(query: str) -> str:
    terms = [
        term
        for chunk in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", query)
        for term in _chunk_terms(chunk)
    ]
    return " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in dict.fromkeys(terms))


class FtsMemoryIndex:
    """Trigram FTS5 index keyed by the semantic fact id."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def ensure_schema(self) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts "
                "USING fts5(content, chat_key UNINDEXED, tokenize='trigram')"
            )
            await conn.commit()

    async def upsert(self, fact: SemanticFact) -> None:
        if fact.fact_id <= 0:
            raise ValueError("FTS upsert requires a persisted fact_id")
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO memory_fts(rowid, content, chat_key) VALUES (?,?,?)",
                (fact.fact_id, fact.fact_text, fact.chat_key),
            )
            await conn.commit()

    async def search(
        self, query: str, chat_key: str = "", limit: int = 20,
    ) -> tuple[int, ...]:
        text = query.strip()
        if not text:
            return ()
        match = _query_terms(text)
        if not match:
            return ()
        async with self._db.connect() as conn:
            if chat_key:
                cursor = await conn.execute(
                    "SELECT rowid FROM memory_fts WHERE memory_fts MATCH ? "
                    "AND chat_key IN (?, 'global') ORDER BY rank LIMIT ?",
                    (match, chat_key, limit),
                )
            else:
                cursor = await conn.execute(
                    "SELECT rowid FROM memory_fts WHERE memory_fts MATCH ? "
                    "ORDER BY rank LIMIT ?", (match, limit),
                )
            rows = await cursor.fetchall()
        return tuple(int(row[0]) for row in rows)
