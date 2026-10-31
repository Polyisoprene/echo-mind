"""Append-only trait evidence store (split from working state for ISP/SRP)."""

from __future__ import annotations

import time
from typing import Any, cast

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.trait_lifecycle import TraitEvidenceStats, assess_lifecycle


def _row(row: aiosqlite.Row) -> TraitEvidence:
    return TraitEvidence(
        evidence_id=int(row[0]), trait_id=int(row[1]), session_id=str(row[2]),
        turn_id=str(row[3]), quote=str(row[4]), quote_kind=cast(Any, str(row[5])),
        polarity=cast(Any, int(row[6])), context_hash=str(row[7]),
        created_ms=int(row[8]),
    )


class SqliteTraitEvidenceStore:
    """Persist/read trait evidence; dedupe is enforced by the DB unique key."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def record_trait_evidence(self, evidence: TraitEvidence) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO trait_evidence "
                "(trait_id, session_id, turn_id, quote, quote_kind, polarity, "
                "context_hash, created_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (evidence.trait_id, evidence.session_id, evidence.turn_id,
                 evidence.quote, evidence.quote_kind, evidence.polarity,
                 evidence.context_hash, evidence.created_ms),
            )
            await conn.commit()

    async def list_trait_evidence(
        self, trait_id: int, limit: int = 50
    ) -> tuple[TraitEvidence, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id, trait_id, session_id, turn_id, quote, quote_kind, "
                "polarity, context_hash, created_ms FROM trait_evidence "
                "WHERE trait_id = ? ORDER BY created_ms DESC, id DESC LIMIT ?",
                (trait_id, limit),
            )
            return tuple(_row(row) for row in await cursor.fetchall())

    async def refresh_lifecycle(self, trait_id: int) -> str:
        """Recompute shadow status from distinct contexts and persist it."""
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT polarity, context_hash, created_ms FROM trait_evidence "
                "WHERE trait_id = ?", (trait_id,),
            )
            rows = await cursor.fetchall()
            supports = {str(r[1]) for r in rows if int(r[0]) > 0}
            contradictions = {str(r[1]) for r in rows if int(r[0]) < 0}
            last_support = max((int(r[2]) for r in rows if int(r[0]) > 0), default=0)
            last_contra = max((int(r[2]) for r in rows if int(r[0]) < 0), default=0)
            stats = TraitEvidenceStats(
                frozenset(supports), frozenset(contradictions),
                last_support, last_contra,
            )
            lifecycle = assess_lifecycle(stats)
            cursor = await conn.execute(
                "SELECT active_since_ms FROM persona_traits WHERE id=?", (trait_id,)
            )
            current = await cursor.fetchone()
            previous_active = int(current[0]) if current else 0
            now_ms = int(time.time() * 1000)
            active_since = (
                previous_active or now_ms
            ) if lifecycle.status == "active" else 0
            await conn.execute(
                "UPDATE persona_traits SET status=?, active_since_ms=?, "
                "last_support_ms=?, last_contradiction_ms=? WHERE id=?",
                (lifecycle.status, active_since, last_support, last_contra, trait_id),
            )
            await conn.commit()
            return lifecycle.status
