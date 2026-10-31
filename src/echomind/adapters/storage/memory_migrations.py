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


KNOWLEDGE_DDL = """
CREATE TABLE IF NOT EXISTS disclosures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_kind TEXT NOT NULL,
  memory_id INTEGER NOT NULL,
  venue TEXT NOT NULL,
  audience_json TEXT NOT NULL,
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  phase TEXT NOT NULL DEFAULT 'gate',
  persona_json TEXT NOT NULL DEFAULT '{}',
  ts_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_knowledge (
  memory_kind TEXT NOT NULL,
  memory_id INTEGER NOT NULL,
  person_id TEXT NOT NULL,
  state TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0,
  updated_ms INTEGER NOT NULL,
  PRIMARY KEY(memory_kind, memory_id, person_id)
);
CREATE TABLE IF NOT EXISTS disclosure_grants (
  memory_kind TEXT NOT NULL,
  memory_id INTEGER NOT NULL,
  grantee_id TEXT NOT NULL,
  granted_by TEXT NOT NULL,
  granted_ms INTEGER NOT NULL,
  expires_ms INTEGER,
  PRIMARY KEY(memory_kind, memory_id, grantee_id)
);
"""


async def ensure_columns(conn: aiosqlite.Connection) -> None:
    await conn.executescript(KNOWLEDGE_DDL)
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
