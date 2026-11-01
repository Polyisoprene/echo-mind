"""Pure reply attribution from chat messages; shadow only."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from echomind.domain.interaction_outcome import InteractionOutcome

# Empirical: direct reply p95 = 1371.9s over 1,709 self messages; round to 30 min.
RESPONSE_WINDOW_MS = 1_800_000


@dataclass(frozen=True)
class ChatMessageRow:
    message_id: int
    chat_key: str
    ts: int
    is_self: bool
    sender_id: str
    sender_name: str
    text: str


def attribute_messages(
    rows: Iterable[ChatMessageRow], aliases: tuple[str, ...],
) -> tuple[InteractionOutcome, ...]:
    ordered = sorted(rows, key=lambda row: (row.chat_key, row.ts, row.message_id))
    by_chat: dict[str, list[ChatMessageRow]] = {}
    for row in ordered:
        by_chat.setdefault(row.chat_key, []).append(row)
    outcomes: list[InteractionOutcome] = []
    for chat_key, messages in by_chat.items():
        outcomes.extend(_chat_outcomes(chat_key, messages, aliases))
    return tuple(outcomes)


def _chat_outcomes(
    chat_key: str, messages: list[ChatMessageRow], aliases: tuple[str, ...],
) -> list[InteractionOutcome]:
    outcomes: list[InteractionOutcome] = []
    for index, message in enumerate(messages):
        if not message.is_self:
            continue
        response, attribution = _first_response(messages, index, message.ts, aliases)
        if response is None:
            continue
        outcomes.append(InteractionOutcome(
            self_message_id=message.message_id,
            response_message_id=response.message_id,
            chat_key=chat_key, self_ts=message.ts, response_ts=response.ts,
            delay_ms=response.ts - message.ts, attribution=attribution,
            sender_id=response.sender_id, sender_name=response.sender_name,
            response_text=response.text[:500], created_ms=response.ts,
        ))
    return outcomes

def _first_response(
    messages: list[ChatMessageRow], index: int, self_ts: int,
    aliases: tuple[str, ...],
) -> tuple[ChatMessageRow | None, Literal["mention", "temporal"]]:
    first: ChatMessageRow | None = None
    for response in messages[index + 1:]:
        if response.ts - self_ts > RESPONSE_WINDOW_MS:
            break
        if response.is_self:
            continue
        if first is None:
            first = response
        if any(alias and alias in response.text for alias in aliases):
            return response, "mention"
    return first, "temporal"
