"""HEXACO is an audit, not a fabricated correlation matrix."""

from __future__ import annotations

from echomind.mind.hexaco_coverage import (
    HEXACO_AXES,
    coverage,
    dimension_mapping,
    missing_axes,
)


def test_all_six_axes_are_reported() -> None:
    assert tuple(item.axis for item in coverage()) == HEXACO_AXES


def test_conscientiousness_is_explicitly_missing() -> None:
    assert "Conscientiousness" in missing_axes()
    assert "Honesty-Humility" not in missing_axes()


def test_dimension_mapping_is_categorical_not_numeric() -> None:
    mapping = dict(dimension_mapping())
    assert mapping["guile"] == ("Honesty-Humility",)
    assert isinstance(mapping["warmth"], tuple)
