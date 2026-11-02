"""Port for binding successful outbound sends to BDI intention events."""

from __future__ import annotations

from typing import Protocol


class IIntentionDelivery(Protocol):
    async def mark_delivered(
        self, target_chat_key: str, sent_texts: tuple[str, ...],
        message_ids: tuple[str, ...],
    ) -> int: ...
