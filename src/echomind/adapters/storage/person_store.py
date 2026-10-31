"""Persist one relationship per person plus the per-venue faces."""

from __future__ import annotations

import time

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.person_level import PersonProfile, build_profiles


def _seen(rows: list[SocialBondProfile]) -> tuple[int, int]:
    first = min((b.last_seen_ms for b in rows if b.last_seen_ms), default=0)
    last = max((b.last_seen_ms for b in rows), default=0)
    return first, last


async def _save_person(
    conn: aiosqlite.Connection,
    person_id: str,
    profile: PersonProfile,
    rows: list[SocialBondProfile],
    now: int,
) -> None:
    name = rows[0].user_name if rows else ""
    first, last = _seen(rows)
    await conn.execute(
        "INSERT INTO persons (person_id, display_name, aliases_json, "
        "first_seen_ms, last_seen_ms) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(person_id) DO UPDATE SET display_name=excluded.display_name, "
        "first_seen_ms=excluded.first_seen_ms, last_seen_ms=excluded.last_seen_ms",
        (person_id, name, "[]", first, last),
    )
    await conn.execute(
        "INSERT INTO person_bonds (person_id, trust, affinity, depth_raw, "
        "depth_percentile, updated_ms) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(person_id) DO UPDATE SET trust=excluded.trust, "
        "affinity=excluded.affinity, depth_raw=excluded.depth_raw, "
        "depth_percentile=excluded.depth_percentile, updated_ms=excluded.updated_ms",
        (person_id, profile.trust, profile.affinity, profile.depth_raw,
         profile.depth_percentile, now),
    )
    for bond in rows:
        await conn.execute(
            "INSERT INTO bond_venues (person_id, venue_id, affinity, msg_count, "
            "role, is_rival, updated_ms) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(person_id, venue_id) DO UPDATE SET "
            "affinity=excluded.affinity, msg_count=excluded.msg_count, "
            "role=excluded.role, is_rival=excluded.is_rival, "
            "updated_ms=excluded.updated_ms",
            (person_id, bond.chat_key, bond.affinity_score, bond.msg_count,
             bond.group_role, int(bond.is_rival), now),
        )


class SqlitePersonStore:
    """Write-through store for person-level profiles; the service computes them."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def save(
        self, profiles: dict[str, PersonProfile], bonds: tuple[SocialBondProfile, ...]
    ) -> None:
        now = int(time.time() * 1000)
        by_person: dict[str, list[SocialBondProfile]] = {}
        for bond in bonds:
            by_person.setdefault(bond.user_id, []).append(bond)
        async with self._db.connect() as conn:
            for person_id, profile in profiles.items():
                await _save_person(conn, person_id, profile, by_person.get(person_id, []), now)
            await conn.commit()

    async def load(self) -> dict[str, PersonProfile]:
        async with self._db.connect() as conn:
            rows = await (await conn.execute(
                "SELECT person_id, trust, affinity, depth_raw, depth_percentile "
                "FROM person_bonds"
            )).fetchall()
        return {
            str(r[0]): PersonProfile(
                person_id=str(r[0]), trust=float(r[1]), affinity=float(r[2]),
                depth_raw=float(r[3]), depth_percentile=float(r[4]),
            )
            for r in rows
        }

    async def sync_from(
        self, bonds: tuple[SocialBondProfile, ...], stats: tuple[BondDepthStats, ...]
    ) -> int:
        """Build profiles from the given rows and persist them; returns the count."""
        profiles = build_profiles(bonds, stats)
        await self.save(profiles, bonds)
        return len(profiles)


__all__ = ["SqlitePersonStore"]
