"""BDI-style bounded intention stack; no automatic extraction from chatter."""

from __future__ import annotations

from echomind.domain.models import IntentionItem

MAX_INTENTIONS = 3


def push_intention(
    items: tuple[IntentionItem, ...], item: IntentionItem,
) -> tuple[IntentionItem, ...]:
    """Append a commitment, deduplicate by summary+target, and cap at three."""
    for existing in items:
        if (existing.summary, existing.target_user_id) == (item.summary, item.target_user_id):
            return items
    kept = (*items, item)
    return kept[-MAX_INTENTIONS:]


def expire_intentions(
    items: tuple[IntentionItem, ...], now_ms: int,
) -> tuple[IntentionItem, ...]:
    """Remove intentions whose TTL has elapsed; zero means no expiry."""
    return tuple(item for item in items if item.expires_at_ms <= 0 or item.expires_at_ms > now_ms)
