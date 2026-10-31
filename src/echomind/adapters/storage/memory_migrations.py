"""Idempotent column migrations for memory provenance and trace fields."""

from __future__ import annotations

import aiosqlite


async def _ensure_column(
    conn: aiosqlite.Connection, table: str, column: str, decl: str
) -> None:
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    if column not in {str(row[1]) for row in rows}:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


async def ensure_columns(conn: aiosqlite.Connection) -> None:
    await _ensure_column(conn, "llm_traces", "chat_key", "TEXT NOT NULL DEFAULT ''")
    await _ensure_column(conn, "stickers", "scene_tags", "TEXT NOT NULL DEFAULT ''")
    await _ensure_column(conn, "turn_traces", "context_count", "INTEGER NOT NULL DEFAULT 0")
    await _ensure_column(conn, "turn_traces", "trigger_count", "INTEGER NOT NULL DEFAULT 0")
    await _ensure_column(conn, "turn_traces", "system_prompt", "TEXT NOT NULL DEFAULT ''")
    await _ensure_column(conn, "turn_traces", "user_prompt", "TEXT NOT NULL DEFAULT ''")
    await _ensure_column(conn, "social_bonds", "bond_depth", "REAL NOT NULL DEFAULT 0.0")
    for table in ("semantic_facts", "episodic_memories"):
        await _ensure_column(conn, table, "scope", "TEXT NOT NULL DEFAULT 'venue'")
        await _ensure_column(conn, table, "source_person_id", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(conn, table, "source_venue_id", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(conn, table, "owner_id", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(conn, table, "sensitivity", "TEXT NOT NULL DEFAULT 'group'")
        await _ensure_column(conn, table, "audience_json", "TEXT NOT NULL DEFAULT '[]'")
        await _ensure_column(conn, table, "source_quote", "TEXT NOT NULL DEFAULT ''")
    await conn.execute(
        "UPDATE semantic_facts SET source_venue_id=chat_key WHERE source_venue_id=''"
    )
    await conn.execute("UPDATE semantic_facts SET scope='global' WHERE chat_key='global'")
    await conn.execute(
        "UPDATE episodic_memories SET source_venue_id=chat_key WHERE source_venue_id=''"
    )
