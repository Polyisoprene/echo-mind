"""Extract the quote/context fields for a trait evidence row."""

from __future__ import annotations

import hashlib
from typing import Literal

from echomind.domain.models import TurnOutcome


def trait_quote(
    outcome: TurnOutcome,
) -> tuple[Literal["assistant", "user", "tool"], str] | None:
    for text in reversed(outcome.sent_texts):
        if text.strip():
            return "assistant", text.strip()
    for percept in reversed(outcome.triggers):
        if percept.text.strip():
            return "user", percept.text.strip()
    if outcome.tools_used:
        return "tool", outcome.tools_used[-1]
    return None


def evidence_context(outcome: TurnOutcome, now_ms: int) -> str:
    audience = sorted({p.sender_id for p in outcome.triggers if p.sender_id})
    raw = f"{outcome.chat_key}|{','.join(audience)}|{now_ms // 86_400_000}"
    return hashlib.sha256(raw.encode()).hexdigest()
