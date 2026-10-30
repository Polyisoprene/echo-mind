"""Stage 30 S30-5: idempotent schema migrations that outgrew the main DDL file."""

from __future__ import annotations

from typing import Any


async def _ensure_column(conn: Any, table: str, column: str, ddl: str) -> None:
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in await cursor.fetchall()}
    if column not in existing:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


async def ensure_trait_columns(conn: Any) -> None:
    """Add provenance columns to persona_traits (chat origin, evidence, last use)."""
    for column, ddl in (
        ("chat_key", "TEXT NOT NULL DEFAULT ''"),
        ("source", "TEXT NOT NULL DEFAULT ''"),
        ("last_used_ms", "INTEGER NOT NULL DEFAULT 0"),
    ):
        await _ensure_column(conn, "persona_traits", column, ddl)
