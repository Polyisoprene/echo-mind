"""Stage 29-B: four-layer weight adaptation (group normalization, calibration, shrinkage, drift)."""

from __future__ import annotations

import pytest

from echomind.domain.bond_stats import BondDepthStats
from echomind.mind.bond_adapt import (
    GroupCalibration,
    PageHinkley,
    apply_calibration,
    fit_affine,
    normalize_group,
    percentile_rank,
    shrink_weights,
)


def test_percentile_rank_is_group_relative() -> None:
    assert percentile_rank((10.0, 20.0, 30.0, 40.0)) == (0.0, 1 / 3, 2 / 3, 1.0)
    assert percentile_rank((5.0, 5.0)) == (0.5, 0.5)
    assert percentile_rank((7.0,)) == (0.5,)


def test_normalize_group_makes_big_and_small_groups_comparable() -> None:
    big = tuple(
        BondDepthStats(chat_key="big", user_id=f"u{i}", msgs=40 * (i + 1), her_msgs=20,
                       responded_to_her=i, sessions=i + 1, impact_sum=10.0, impact_n=10)
        for i in range(10)
    )
    small = (
        BondDepthStats(chat_key="small", user_id="s0", msgs=4, her_msgs=2, responded_to_her=1,
                       sessions=2, impact_sum=4.0, impact_n=4),
        BondDepthStats(chat_key="small", user_id="s1", msgs=8, her_msgs=3, responded_to_her=2,
                       sessions=3, impact_sum=8.0, impact_n=4),
    )
    big_norm = normalize_group(big)
    small_norm = normalize_group(small)
    # Top member of the small group reaches the same relative position as the big group's top.
    assert big_norm[-1].frequency == pytest.approx(1.0)
    assert small_norm[-1].frequency == pytest.approx(1.0)
    assert big_norm[0].frequency == pytest.approx(0.0)
    assert small_norm[0].frequency == pytest.approx(0.0)


def test_shrinkage_trusts_global_when_local_data_is_thin() -> None:
    local, prior = (2.0, 0.0, 0.0), (1.0, 0.0, 0.0)
    thin = shrink_weights(local, prior, n_obs=2, tau=4.0)
    rich = shrink_weights(local, prior, n_obs=400, tau=4.0)
    assert prior[0] < thin[0] < rich[0] <= local[0] + 1e-9
    assert rich[0] == pytest.approx(2.0, abs=0.05)


def test_affine_calibration_recovers_slope_and_offset() -> None:
    xs = tuple(float(i) for i in range(30))
    ys = tuple(2.0 * x + 1.0 for x in xs)
    calib = fit_affine(xs, ys)
    assert calib.slope == pytest.approx(2.0, abs=0.01)
    assert calib.offset == pytest.approx(1.0, abs=0.05)
    assert apply_calibration(10.0, calib) == pytest.approx(21.0, abs=0.2)


def test_affine_calibration_stays_identity_when_data_is_thin() -> None:
    calib = fit_affine((1.0, 2.0, 3.0), (5.0, 9.0, 2.0))
    assert (calib.slope, calib.offset) == (1.0, 0.0)
    assert apply_calibration(42.0, GroupCalibration(chat_key="g")) == 42.0


def test_page_hinkley_detects_a_level_shift() -> None:
    detector = PageHinkley(delta=0.01, threshold=0.5)
    quiet = [detector.update(0.50 + (0.001 if i % 2 else -0.001)) for i in range(40)]
    assert not any(quiet), "a stationary stream must not raise an alarm"
    alarmed = [detector.update(0.80) for _ in range(40)]
    assert any(alarmed), "a level shift must raise an alarm"
