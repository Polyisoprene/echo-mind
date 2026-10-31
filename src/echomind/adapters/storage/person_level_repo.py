"""Read-only queries that collapse venue rows into one person-level view."""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile

RoleType = Literal["owner", "admin", "member"]

BOND_SQL = (
    "SELECT chat_key, user_id, user_name, group_role, affinity_score, affinity_level, "
    "msg_count, trust_score, bond_depth, is_rival, rival_reason, traits_json "
    "FROM social_bonds"
)
STATS_SQL = (
    "SELECT chat_key, user_id, msgs, sessions, responded_to_her, her_msgs, "
    "replies_to_them, impact_sum, impact_n, betrayals FROM bond_depth_stats"
)


async def load_bonds(db: SqliteDatabase) -> tuple[SocialBondProfile, ...]:
    async with db.connect() as conn:
        rows = await (await conn.execute(BOND_SQL)).fetchall()
    return tuple(_bond(row) for row in rows)


async def load_stats(db: SqliteDatabase) -> tuple[BondDepthStats, ...]:
    async with db.connect() as conn:
        rows = await (await conn.execute(STATS_SQL)).fetchall()
    return tuple(
        BondDepthStats(
            chat_key=str(r[0]), user_id=str(r[1]), msgs=int(r[2]), sessions=int(r[3]),
            responded_to_her=int(r[4]), her_msgs=int(r[5]), replies_to_them=int(r[6]),
            impact_sum=float(r[7]), impact_n=int(r[8]), betrayals=int(r[9]),
        )
        for r in rows
    )


def _bond(row: Any) -> SocialBondProfile:
    role = str(row[3])
    return SocialBondProfile(
        chat_key=str(row[0]), user_id=str(row[1]), user_name=str(row[2]),
        group_role=cast(RoleType, role) if role in ("owner", "admin", "member") else "member",
        affinity_score=float(row[4]), affinity_level=int(row[5]), msg_count=int(row[6]),
        trust_score=float(row[7]), bond_depth=float(row[8]), is_rival=bool(row[9]),
        rival_reason=str(row[10]),
        traits=tuple(str(t) for t in json.loads(str(row[11] or "[]")) if t),
    )


__all__ = ["load_bonds", "load_stats"]
