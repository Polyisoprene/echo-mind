"""Source/audience policy for cross-session recall; pure and side-effect free."""

from __future__ import annotations

from dataclasses import dataclass

_SENSITIVITY = frozenset({"public", "group", "private", "secret"})


@dataclass(frozen=True)
class RecallRequest:
    source_chat: str
    current_chat: str
    sensitivity: str
    audience: tuple[str, ...] = ()


def can_recall_across_sessions(request: RecallRequest) -> bool:
    """Apply contextual-integrity rules; secret never crosses its audience."""
    if request.source_chat == request.current_chat:
        return True
    if request.sensitivity not in _SENSITIVITY:
        return False
    if request.sensitivity == "secret":
        return False
    if request.sensitivity == "private":
        return False
    restricted = bool(request.audience and request.current_chat not in request.audience)
    return not restricted
