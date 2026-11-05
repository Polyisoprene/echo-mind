"""Shared numeric helpers for the pure-strategy layers.

These live in `domain/` because both `mind/` and `adapters/` need them and the
architecture contract forbids `mind/` from importing infrastructure packages.

Why this module exists: six near-identical `_clamp` helpers had drifted across
the codebase with three different rounding behaviours (3 decimals / 2 decimals
/ none) and two different evaluation orders (round-then-bound vs bound-then-
round). The order matters whenever a value overshoots its bound: rounding
first returns the rounded input, bounding first returns the exact bound. Both
orderings are reproduced below so call sites keep their current numbers.
"""

from __future__ import annotations

# [lower, upper] default band for 0..100 dimensions; literal on purpose so it is
# not mistaken for a tunable parameter (the ledger tracks those).


def clamp(
    value: float,
    lower: float = 0.0,
    upper: float = 100.0,
    *,
    digits: int | None = None,
) -> float:
    """Bound `value` into [lower, upper], then round to `digits` decimals.

    Use this when the bound is the final authority (salience, temperatures).
    Rounding stays explicit so each caller's precision choice is visible.
    """
    bounded = max(lower, min(upper, value))
    return round(bounded, digits) if digits is not None else bounded


def clamp_rounded(
    value: float,
    lower: float = 0.0,
    upper: float = 100.0,
    *,
    digits: int = 2,
) -> float:
    """Round `value` to `digits` decimals first, then bound it into [lower, upper].

    Use this for accumulating state (drives, affect) where the pre-clamp value
    carries more precision than the dimension is meant to store.
    """
    return max(lower, min(upper, round(value, digits)))


def clamp01(value: float, *, digits: int | None = None) -> float:
    """Clamp into the unit interval [0.0, 1.0]."""
    return clamp(value, 0.0, 1.0, digits=digits)


def clamp_int(value: object, lower: int, upper: int, default: int = 0) -> int:
    """Best-effort integer clamp used when parsing LLM output; falls back to `default`."""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return max(lower, min(upper, int(value)))
    except (TypeError, ValueError):
        return default


__all__ = [
    "clamp",
    "clamp01",
    "clamp_int",
    "clamp_rounded",
]
