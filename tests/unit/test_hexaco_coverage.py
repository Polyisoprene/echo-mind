"""HEXACO is an audit, not a fabricated correlation matrix."""

from __future__ import annotations

from echomind.mind.hexaco_coverage import HEXACO_AXES, coverage, missing_axes


def test_all_six_axes_are_reported() -> None:
    assert tuple(item.axis for item in coverage()) == HEXACO_AXES


def test_conscientiousness_is_explicitly_missing() -> None:
    assert "Conscientiousness" in missing_axes()
    assert "Honesty-Humility" not in missing_axes()
