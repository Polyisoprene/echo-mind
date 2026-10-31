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
CREATE TABLE IF NOT EXISTS memory_vectors (
  memory_kind TEXT NOT NULL,
  memory_id INTEGER NOT NULL,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector_json TEXT NOT NULL,
  updated_ms INTEGER NOT NULL,
  PRIMARY KEY(memory_kind, memory_id)
);
CREATE TABLE IF NOT EXISTS persons (
  person_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL DEFAULT '',
  aliases_json TEXT NOT NULL DEFAULT '[]',
  first_seen_ms INTEGER NOT NULL DEFAULT 0,
  last_seen_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS person_bonds (
  person_id TEXT PRIMARY KEY,
  trust REAL NOT NULL DEFAULT 0,
  affinity REAL NOT NULL DEFAULT 0,
  depth_raw REAL NOT NULL DEFAULT 0,
  depth_percentile REAL NOT NULL DEFAULT 0,
  updated_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bond_venues (
  person_id TEXT NOT NULL,
  venue_id TEXT NOT NULL,
  affinity REAL NOT NULL DEFAULT 0,
  msg_count INTEGER NOT NULL DEFAULT 0,
  role TEXT NOT NULL DEFAULT 'member',
  is_rival INTEGER NOT NULL DEFAULT 0,
  updated_ms INTEGER NOT NULL,
  PRIMARY KEY(person_id, venue_id)
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
    await conn.executescript(KNOWLEDGE_SYNC_DDL)

KNOWLEDGE_SYNC_DDL = """
CREATE TABLE IF NOT EXISTS sensitivity_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_kind TEXT NOT NULL,
  memory_id INTEGER NOT NULL,
  from_sensitivity TEXT NOT NULL,
  to_sensitivity TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reason TEXT NOT NULL,
  ts_ms INTEGER NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_fact_known_ins AFTER INSERT ON semantic_facts
BEGIN
  INSERT OR IGNORE INTO memory_knowledge
    (memory_kind, memory_id, person_id, state, confidence, updated_ms)
  SELECT 'semantic', NEW.id, NEW.source_person_id, 'told_to_me', 1.0,
         CAST(strftime('%s','now') AS INTEGER) * 1000
  WHERE NEW.source_person_id <> '';
  INSERT OR IGNORE INTO memory_knowledge
    (memory_kind, memory_id, person_id, state, confidence, updated_ms)
  SELECT 'semantic', NEW.id, NEW.owner_id, 'knows', 1.0,
         CAST(strftime('%s','now') AS INTEGER) * 1000
  WHERE NEW.owner_id <> '' AND NEW.owner_id <> NEW.source_person_id;
END;
CREATE TRIGGER IF NOT EXISTS trg_fact_known_upd
AFTER UPDATE OF source_person_id, owner_id ON semantic_facts
BEGIN
  INSERT OR IGNORE INTO memory_knowledge
    (memory_kind, memory_id, person_id, state, confidence, updated_ms)
  SELECT 'semantic', NEW.id, NEW.source_person_id, 'told_to_me', 1.0,
         CAST(strftime('%s','now') AS INTEGER) * 1000
  WHERE NEW.source_person_id <> '';
  INSERT OR IGNORE INTO memory_knowledge
    (memory_kind, memory_id, person_id, state, confidence, updated_ms)
  SELECT 'semantic', NEW.id, NEW.owner_id, 'knows', 1.0,
         CAST(strftime('%s','now') AS INTEGER) * 1000
  WHERE NEW.owner_id <> '' AND NEW.owner_id <> NEW.source_person_id;
END;
CREATE TRIGGER IF NOT EXISTS trg_episode_known_ins AFTER INSERT ON episodic_memories
BEGIN
  INSERT OR IGNORE INTO memory_knowledge
    (memory_kind, memory_id, person_id, state, confidence, updated_ms)
  SELECT 'episodic', NEW.id, NEW.source_person_id, 'told_to_me', 1.0,
         CAST(strftime('%s','now') AS INTEGER) * 1000
  WHERE NEW.source_person_id <> '';
  INSERT OR IGNORE INTO memory_knowledge
    (memory_kind, memory_id, person_id, state, confidence, updated_ms)
  SELECT 'episodic', NEW.id, NEW.owner_id, 'knows', 1.0,
         CAST(strftime('%s','now') AS INTEGER) * 1000
  WHERE NEW.owner_id <> '' AND NEW.owner_id <> NEW.source_person_id;
END;
INSERT OR IGNORE INTO memory_knowledge
  (memory_kind, memory_id, person_id, state, confidence, updated_ms)
SELECT 'semantic', id, source_person_id, 'told_to_me', 1.0,
       CAST(strftime('%s','now') AS INTEGER) * 1000
FROM semantic_facts WHERE source_person_id <> '';
INSERT OR IGNORE INTO memory_knowledge
  (memory_kind, memory_id, person_id, state, confidence, updated_ms)
SELECT 'semantic', id, owner_id, 'knows', 1.0,
       CAST(strftime('%s','now') AS INTEGER) * 1000
FROM semantic_facts WHERE owner_id <> '' AND owner_id <> source_person_id;
INSERT OR IGNORE INTO memory_knowledge
  (memory_kind, memory_id, person_id, state, confidence, updated_ms)
SELECT 'episodic', id, source_person_id, 'told_to_me', 1.0,
       CAST(strftime('%s','now') AS INTEGER) * 1000
FROM episodic_memories WHERE source_person_id <> '';
INSERT OR IGNORE INTO memory_knowledge
  (memory_kind, memory_id, person_id, state, confidence, updated_ms)
SELECT 'episodic', id, owner_id, 'knows', 1.0,
       CAST(strftime('%s','now') AS INTEGER) * 1000
FROM episodic_memories WHERE owner_id <> '' AND owner_id <> source_person_id;
"""
