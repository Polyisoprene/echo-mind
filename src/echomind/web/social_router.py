"""Console endpoint: how many speakers the bot has seen versus how many it has bonded."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from echomind.core.bootstrap import EchoMindContainer


def build_social_router(container: EchoMindContainer) -> APIRouter:
    """Social coverage stats for one chat."""
    router = APIRouter()

    async def _count(sql: str, chat_key: str) -> int:
        async with container.db.connect() as conn:
            row = await (await conn.execute(sql, (chat_key,))).fetchone()
        return int(row[0]) if row else 0

    @router.get("/api/mind/social-coverage")
    async def social_coverage(chat_key: str) -> dict[str, Any]:
        speakers = await _count(
            "SELECT COUNT(DISTINCT sender_id) FROM chat_messages "
            "WHERE chat_key = ? AND is_self = 0", chat_key,
        )
        bonds = await _count("SELECT COUNT(*) FROM social_bonds WHERE chat_key = ?", chat_key)
        interacted = await _count(
            "SELECT COUNT(*) FROM social_bonds WHERE chat_key = ? AND bond_depth > 0", chat_key
        )
        return {"ok": True, "speakers": speakers, "bonds": bonds, "interacted": interacted}

    return router
