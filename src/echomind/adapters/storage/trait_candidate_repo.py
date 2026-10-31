"""Persist generated trait candidates separately from active persona traits."""

from __future__ import annotations

import time
from typing import Any, cast

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.trait_candidate import TraitCandidate


def _row(row: aiosqlite.Row) -> TraitCandidate:
    return TraitCandidate(
        candidate_id=int(row[0]), trait_id=int(row[1]),
        category=cast(Any, str(row[2])), trait_text=str(row[3]),
        evidence_json=str(row[4]), prompt_hash=str(row[5]),
        generator_model=str(row[6]), status=cast(Any, str(row[7])),
        reject_reason=str(row[8]), created_ms=int(row[9]),
    )


class SqliteTraitCandidateStore:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def save_candidate(self, candidate: TraitCandidate) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO trait_candidates "
                "(trait_id, category, trait_text, evidence_json, prompt_hash, "
                "generator_model, status, reject_reason, created_ms) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (candidate.trait_id, candidate.category, candidate.trait_text,
                 candidate.evidence_json, candidate.prompt_hash,
                 candidate.generator_model, candidate.status,
                 candidate.reject_reason, int(time.time() * 1000)),
            )
            await conn.commit()

    async def list_candidates(
        self, trait_id: int, limit: int = 20
    ) -> tuple[TraitCandidate, ...]:
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT id, trait_id, category, trait_text, evidence_json, "
                "prompt_hash, generator_model, status, reject_reason, created_ms "
                "FROM trait_candidates WHERE trait_id=? ORDER BY id DESC LIMIT ?",
                (trait_id, limit),
            )
            return tuple(_row(row) for row in await cursor.fetchall())
