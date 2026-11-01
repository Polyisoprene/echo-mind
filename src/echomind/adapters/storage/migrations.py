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
        ("evidence_count", "INTEGER NOT NULL DEFAULT 1"),
        ("contradiction_count", "INTEGER NOT NULL DEFAULT 0"),
        ("last_evidence_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("status", "TEXT NOT NULL DEFAULT 'legacy_unverified'"),
        ("active_since_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("last_support_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("last_contradiction_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("state_n", "INTEGER NOT NULL DEFAULT 0"),
        ("state_mean", "REAL NOT NULL DEFAULT 0"),
        ("state_m2", "REAL NOT NULL DEFAULT 0"),
    ):
        await _ensure_column(conn, "persona_traits", column, ddl)


_CLAIM_DDL = """
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL DEFAULT 'value',
    value TEXT NOT NULL,
    valid_from_ms INTEGER NOT NULL DEFAULT 0,
    valid_to_ms INTEGER,
    recorded_at_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'asserted',
    superseded_by INTEGER,
    created_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_claims_lookup ON claims (chat_key, subject, predicate, status);
CREATE TABLE IF NOT EXISTS claim_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    weight REAL NOT NULL DEFAULT 0.5,
    observed_at_ms INTEGER NOT NULL DEFAULT 0,
    raw_text TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim ON claim_evidence (claim_id);
CREATE TABLE IF NOT EXISTS fact_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL DEFAULT 'value',
    reason TEXT NOT NULL DEFAULT '',
    opened_at_ms INTEGER NOT NULL DEFAULT 0,
    resolved_at_ms INTEGER,
    resolution TEXT NOT NULL DEFAULT ''
);
"""


async def ensure_claim_tables(conn: Any) -> None:
    """Stage 39: claim/evidence/review tables (shadow until reads are switched)."""
    await conn.executescript(_CLAIM_DDL)


_TRAIT_EVIDENCE_DDL = """
CREATE TABLE IF NOT EXISTS trait_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trait_id INTEGER NOT NULL REFERENCES persona_traits(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  quote TEXT NOT NULL,
  quote_kind TEXT NOT NULL CHECK(quote_kind IN ('assistant','user','tool')),
  polarity INTEGER NOT NULL CHECK(polarity IN (-1, 1)),
  context_hash TEXT NOT NULL,
  created_ms INTEGER NOT NULL,
  UNIQUE(trait_id, turn_id, polarity)
);
CREATE INDEX IF NOT EXISTS idx_trait_evidence_trait
  ON trait_evidence(trait_id, created_ms);
"""


async def ensure_trait_evidence_table(conn: Any) -> None:
    """Create the append-only trait evidence ledger."""
    await conn.executescript(_TRAIT_EVIDENCE_DDL)
    await _ensure_column(conn, "trait_evidence", "memory_ids_json", "TEXT NOT NULL DEFAULT '[]'")


_TRAIT_CANDIDATE_DDL = """
CREATE TABLE IF NOT EXISTS trait_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trait_id INTEGER NOT NULL REFERENCES persona_traits(id) ON DELETE CASCADE,
  category TEXT NOT NULL CHECK(category IN ('habit','temperament','taste','taboo')),
  trait_text TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  generator_model TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'candidate'
    CHECK(status IN ('candidate','rejected','promoted')),
  reject_reason TEXT NOT NULL DEFAULT '',
  created_ms INTEGER NOT NULL,
  UNIQUE(trait_id, prompt_hash)
);
CREATE INDEX IF NOT EXISTS idx_trait_candidates_trait
  ON trait_candidates(trait_id, created_ms);
"""


async def ensure_trait_candidate_table(conn: Any) -> None:
    await conn.executescript(_TRAIT_CANDIDATE_DDL)
    for column, ddl in (
        ("promoted_by", "TEXT NOT NULL DEFAULT ''"),
        ("promote_reason", "TEXT NOT NULL DEFAULT ''"),
        ("promoted_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("signature_json", "TEXT NOT NULL DEFAULT '{}'"),
    ):
        await _ensure_column(conn, "trait_candidates", column, ddl)


_TRAIT_MEMORY_DDL = """
CREATE TABLE IF NOT EXISTS trait_memory_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trait_id INTEGER NOT NULL REFERENCES persona_traits(id) ON DELETE CASCADE,
  memory_kind TEXT NOT NULL CHECK(memory_kind IN ('semantic','episodic')),
  memory_id INTEGER NOT NULL CHECK(memory_id > 0),
  relation TEXT NOT NULL DEFAULT 'supports'
    CHECK(relation IN ('supports','contradicts')),
  is_context INTEGER NOT NULL DEFAULT 0,
  evidence_ms INTEGER NOT NULL DEFAULT 0,
  UNIQUE(trait_id, memory_kind, memory_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_trait_memory_trait
  ON trait_memory_links(trait_id, memory_kind);
"""


async def ensure_trait_memory_table(conn: Any) -> None:
    await conn.executescript(_TRAIT_MEMORY_DDL)
    await _ensure_column(conn, "trait_memory_links", "is_context", "INTEGER NOT NULL DEFAULT 0")


_TRAIT_SHADOW_DDL = """
CREATE TABLE IF NOT EXISTS trait_action_shadow (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_key TEXT NOT NULL,
  session_id TEXT NOT NULL,
  trait_ids_json TEXT NOT NULL DEFAULT '[]',
  allowed_tools_json TEXT NOT NULL DEFAULT '[]',
  allow_refusal INTEGER NOT NULL DEFAULT 0,
  actual_tools_json TEXT NOT NULL DEFAULT '[]',
  sent_count INTEGER NOT NULL DEFAULT 0,
  created_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trait_shadow_chat
  ON trait_action_shadow(chat_key, created_ms);
"""


async def ensure_trait_shadow_table(conn: Any) -> None:
    await conn.executescript(_TRAIT_SHADOW_DDL)


async def ensure_migrations(conn: Any) -> None:
    """Run every idempotent migration in one call."""
    await ensure_trait_columns(conn)
    await ensure_trait_evidence_table(conn)
    await ensure_trait_candidate_table(conn)
    await ensure_trait_memory_table(conn)
    await ensure_trait_shadow_table(conn)
    await ensure_claim_tables(conn)
