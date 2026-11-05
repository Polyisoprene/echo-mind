"""Regression: the two clamp orderings must stay distinguishable.

Six near-identical `_clamp` helpers had drifted across the codebase. They shared
a name but not a meaning: some rounded before bounding, some after, one did not
round at all. Unifying them into `domain/numeric.py` kept both orderings, and
these tests exist so a future "cleanup" cannot silently merge them.
"""

from __future__ import annotations

import pytest

from echomind.domain.numeric import clamp, clamp01, clamp_int, clamp_rounded


def test_clamp_bounds_then_rounds() -> None:
    """The bound wins: an overshooting value comes back as the exact bound."""
    assert clamp(137.768, -10.0, 84.693744585, digits=2) == 84.69
    assert clamp(-99.0, 0.0, 1.0, digits=3) == 0.0


def test_clamp_rounded_rounds_then_bounds() -> None:
    """Rounding wins on the input; the bound is then applied verbatim."""
    assert clamp_rounded(137.768, -10.0, 84.693744585, digits=2) == pytest.approx(84.693744585)


def test_the_two_orderings_actually_differ() -> None:
    """Guard against anyone collapsing the two helpers into one."""
    value, lower, upper = 137.768, -10.0, 84.693744585
    assert clamp(value, lower, upper, digits=2) != clamp_rounded(value, lower, upper, digits=2)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.123456, 0.12), (0.129999, 0.13), (-5.0, 0.0), (150.0, 100.0), (50.0, 50.0)],
)
def test_clamp_defaults_to_the_0_100_band_with_two_decimals(
    value: float, expected: float
) -> None:
    assert clamp_rounded(value) == expected


def test_clamp_without_digits_does_not_round() -> None:
    assert clamp(0.123456789) == 0.123456789


def test_clamp01_is_the_unit_interval() -> None:
    assert clamp01(0.5) == 0.5
    assert clamp01(-1.0) == 0.0
    assert clamp01(2.0) == 1.0
    assert clamp01(0.123456, digits=3) == 0.123


@pytest.mark.parametrize(
    ("raw", "lower", "upper", "expected"),
    [("7", 0, 5, 5), (3.9, 0, 9, 3), (100, 0, 5, 5), (None, 0, 5, 0), ("abc", 0, 5, 0)],
)
def test_clamp_int_parses_llm_values(
    raw: object, lower: int, upper: int, expected: int
) -> None:
    assert clamp_int(raw, lower, upper) == expected


def test_clamp_int_keeps_legacy_bool_behaviour() -> None:
    """bool is an int subclass; the historical helper converted it, so does this one."""
    assert clamp_int(True, 0, 5) == 1
