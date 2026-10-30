"""Stage 29 A3b: one-shot reset of legacy owner privileges in social_bonds (D4)."""

from __future__ import annotations

from typing import Any

RESET_SQL = (
    "UPDATE social_bonds SET "
    "affinity_score=CASE WHEN affinity_score>1000 THEN 30.0 ELSE affinity_score END, "
    "trust_score=CASE WHEN trust_score>0.99 THEN 0.75 ELSE trust_score END, "
    "group_role=CASE WHEN group_role='owner' THEN 'member' ELSE group_role END, "
    "bond_depth=0.0 "
    "WHERE affinity_score>1000 OR trust_score>0.99 OR group_role='owner' OR bond_depth<>0.0"
)
COUNT_SQL = (
    "SELECT COUNT(*) FROM social_bonds WHERE affinity_score>1000 OR trust_score>0.99 "
    "OR group_role='owner' OR bond_depth<>0.0"
)


async def reset_privileged_bonds(
    db: Any, *, dry_run: bool = False, reset_stats: bool = True
) -> int:
    """Clamp legacy owner sentinels; optionally wipe counters so depth restarts at zero."""
    async with db.connect() as conn:
        cursor = await conn.execute(COUNT_SQL)
        affected = int((await cursor.fetchone())[0])
        if not dry_run and affected:
            await conn.execute(RESET_SQL)
            await conn.commit()
        if not dry_run and reset_stats:
            await conn.execute("DELETE FROM bond_depth_stats")
            await conn.commit()
    return affected
