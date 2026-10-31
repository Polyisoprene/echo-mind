"""A per-turn shadow record: what active traits would have allowed."""

from __future__ import annotations

from echomind.domain.base import FrozenValueObject


class TraitShadowRecord(FrozenValueObject):
    record_id: int = 0
    chat_key: str
    session_id: str
    trait_ids: tuple[int, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    allow_refusal: bool = False
    actual_tools: tuple[str, ...] = ()
    sent_count: int = 0
    created_ms: int = 0
