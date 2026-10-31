"""E1-F: affinity levels use quantile thresholds fitted on active bonds."""

from __future__ import annotations

from echomind.mind.memory_consolidator import AFFINITY_THRESHOLDS, compute_affinity_level


def test_thresholds_are_the_fitted_quantiles() -> None:
    assert AFFINITY_THRESHOLDS == (31.77, 40.75, 48.2, 56.79)


def test_level_boundaries() -> None:
    assert compute_affinity_level(26.7) == 1
    assert compute_affinity_level(31.76) == 1
    assert compute_affinity_level(31.77) == 2
    assert compute_affinity_level(40.75) == 3
    assert compute_affinity_level(48.2) == 4
    assert compute_affinity_level(56.79) == 5
    assert compute_affinity_level(97.1) == 5


def test_dormant_default_bond_stays_level_one() -> None:
    assert compute_affinity_level(30.0) == 1
