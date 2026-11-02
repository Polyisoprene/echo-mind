"""HEXACO construct coverage audit; no numeric mapping without data."""

from __future__ import annotations

from dataclasses import dataclass

HEXACO_AXES = (
    "Honesty-Humility", "Emotionality", "Extraversion",
    "Agreeableness", "Conscientiousness", "Openness",
)

# Construct-level hypotheses only; None means the 7D model has no independent axis.
_COVERAGE: dict[str, tuple[str, ...]] = {
    "warmth": ("Agreeableness", "Extraversion"),
    "tsundere": ("Emotionality", "Agreeableness"),
    "playfulness": ("Extraversion", "Openness"),
    "possessiveness": ("Emotionality",),
    "confidence": ("Extraversion",),
    "guile": ("Honesty-Humility",),
    "defiance": ("Agreeableness", "Honesty-Humility"),
}


@dataclass(frozen=True)
class AxisCoverage:
    axis: str
    covered_by: tuple[str, ...]


def coverage() -> tuple[AxisCoverage, ...]:
    return tuple(
        AxisCoverage(axis, tuple(
            dim for dim, axes in _COVERAGE.items() if axis in axes
        )) for axis in HEXACO_AXES
    )


def missing_axes() -> tuple[str, ...]:
    return tuple(item.axis for item in coverage() if not item.covered_by)


def dimension_mapping() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Categorical 7D -> HEXACO hypotheses; no numeric weights."""
    return tuple((dim, axes) for dim, axes in _COVERAGE.items())
