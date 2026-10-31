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


async def ensure_migrations(conn: Any) -> None:
    """Run every idempotent migration in one call."""
    await ensure_trait_columns(conn)
    await ensure_claim_tables(conn)
