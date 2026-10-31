"""Stage 44: configurable token budget for hippocampal memory consolidation."""

from __future__ import annotations

DEFAULT_CONSOLIDATION_BUDGET = 900
_BUDGET = DEFAULT_CONSOLIDATION_BUDGET
_THINKING = False


def set_consolidation_budget(value: int | str) -> None:
    """Set the consolidation token budget (clamped to a usable range)."""
    global _BUDGET
    try:
        _BUDGET = max(200, min(4000, int(value)))
    except (TypeError, ValueError):
        _BUDGET = DEFAULT_CONSOLIDATION_BUDGET
_THINKING = False


def set_consolidation_thinking(enabled: bool) -> None:
    """Whether the consolidation call may use thinking mode (default off)."""
    global _THINKING
    _THINKING = bool(enabled)


def consolidation_thinking() -> bool:
    """Current thinking switch for the consolidation call."""
    return _THINKING


def consolidation_budget() -> int:
    """Current budget used by the hippocampal consolidation call."""
    return _BUDGET
