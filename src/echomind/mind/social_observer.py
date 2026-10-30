"""Stage 40: social observation — record everyone she sees, not only whoever wakes her.

The bond table used to grow only inside turn consolidation, so quiet bots under-reported
their social circle. This module builds/refreshes a contact record for every inbound message.
"""

from __future__ import annotations

from typing import Protocol

from echomind.domain.models import Percept, SocialBondProfile
from echomind.mind.memory_consolidator import _default_bond


class _BondReader(Protocol):
    async def get_social_bond(self, chat_key: str, user_id: str) -> SocialBondProfile | None: ...


class _BondWriter(Protocol):
    async def upsert_social_bond(self, bond: SocialBondProfile) -> None: ...


async def observe_contact(
    reader: _BondReader, writer: _BondWriter, percept: Percept, *,
    operator_ids: tuple[str, ...] = (),
) -> SocialBondProfile:
    """Create or refresh a member's bond from a single observed message."""
    chat_key = percept.chat_key
    bond = await reader.get_social_bond(chat_key, percept.sender_id)
    if bond is None:
        bond = _default_bond(chat_key, percept, percept.sender_id in operator_ids)
    updated = bond.model_copy(update={
        "user_name": percept.sender_name or bond.user_name,
        "msg_count": bond.msg_count + 1,
        "last_seen_ms": percept.timestamp_ms,
    })
    await writer.upsert_social_bond(updated)
    return updated
