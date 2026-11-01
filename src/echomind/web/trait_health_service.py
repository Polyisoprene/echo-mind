"""Read-only trait-health projection for the inspector API."""

from __future__ import annotations

from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.mind.trait_health import TraitHealth


def _int_row(row: Any, index: int = 0) -> int:
    return 0 if row is None else int(row[index])


async def trait_health(db: SqliteDatabase) -> dict[str, Any]:
    async with db.connect() as conn:
        active = await (await conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(active_since_ms), 0) "
            "FROM persona_traits WHERE status='active'"
        )).fetchone()
        active_count = _int_row(active)
        active_since = _int_row(active, 1)
        shadow = _int_row(await (await conn.execute(
            "SELECT COUNT(*) FROM trait_action_shadow WHERE created_ms >= ?",
            (active_since,),
        )).fetchone())
        nonempty = _int_row(await (await conn.execute(
            "SELECT COUNT(*) FROM trait_action_shadow WHERE created_ms >= ? "
            "AND trait_ids_json != '[]'", (active_since,),
        )).fetchone())
        links = _int_row(await (await conn.execute(
            "SELECT COUNT(*) FROM trait_memory_links WHERE relation='supports' AND is_context=0"
        )).fetchone())
        latest = _int_row(await (await conn.execute(
            "SELECT COALESCE(MAX(ts),0) FROM turn_traces"
        )).fetchone())
        facts = _int_row(await (await conn.execute(
            "SELECT COUNT(*) FROM semantic_facts WHERE source_turn_id != ''"
        )).fetchone())
    health = TraitHealth(active_count, shadow, nonempty, links, latest, facts)
    return {
        "status": health.status, "active_traits": health.active_traits,
        "shadow_since_activation": health.shadow_since_activation,
        "nonempty_shadow": health.nonempty_shadow,
        "causal_links": health.causal_links,
        "latest_turn_ms": health.latest_turn_ms,
        "facts_with_turn": health.facts_with_turn,
    }
