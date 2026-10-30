"""Stage 29-B: four-layer adaptation of bond-depth scoring across groups.

L1  group-relative percentile normalization  (TF-IDF/BM25 idea: rank inside the group)
L2  per-group affine calibration            (Platt 1999; Zadrozny & Elkan 2002)
L3  empirical-Bayes shrinkage to a global prior (Gelman & Hill 2007; Efron & Morris 1975)
L4  Page-Hinkley drift detection            (Page 1954) — alarm only, never auto-tunes
"""

from __future__ import annotations

from dataclasses import dataclass

from echomind.domain.bond_stats import BondDepthStats, BondFeatures
from echomind.mind.bond_features import features_from_stats

MIN_OBS_FOR_CALIBRATION = 20
SLOPE_BOUNDS = (0.5, 2.0)
OFFSET_BOUNDS = (-20.0, 20.0)
DEFAULT_TAU = 0.35


@dataclass(frozen=True)
class GroupCalibration:
    """Per-group affine calibration of the raw depth score."""

    chat_key: str
    slope: float = 1.0
    offset: float = 0.0
    n_obs: int = 0


def percentile_rank(values: tuple[float, ...]) -> tuple[float, ...]:
    """Rank values inside their group into [0, 1] with mid-ranks for ties."""
    n = len(values)
    if n <= 1:
        return tuple(0.5 for _ in values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    pos = 0
    while pos < n:
        end = pos
        while end + 1 < n and values[order[end + 1]] == values[order[pos]]:
            end += 1
        mid = (pos + end) / 2.0
        for k in range(pos, end + 1):
            ranks[order[k]] = mid / (n - 1)
        pos = end + 1
    return tuple(ranks)


def _columns(features: tuple[BondFeatures, ...]) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(getattr(f, name) for f in features) for name in (
        "frequency", "diversity", "responsivity", "reciprocity", "impact", "betrayal",
    ))


def normalize_group(stats: tuple[BondDepthStats, ...]) -> tuple[BondFeatures, ...]:
    """L1: replace absolute features with within-group percentile ranks."""
    if not stats:
        return ()
    raw = tuple(features_from_stats(s) for s in stats)
    cols = tuple(percentile_rank(col) for col in _columns(raw))
    names = ("frequency", "diversity", "responsivity", "reciprocity", "impact")
    return tuple(
        BondFeatures(
            **{name: round(cols[idx][i], 4) for idx, name in enumerate(names)},
            betrayal=round(raw[i].betrayal, 4),
        )
        for i in range(len(stats))
    )


def shrink_weights(
    local: tuple[float, ...], prior: tuple[float, ...], *, n_obs: int, tau: float = DEFAULT_TAU
) -> tuple[float, ...]:
    """L3: empirical-Bayes shrink local weights toward the global prior."""
    if not local or len(local) != len(prior):
        return prior
    weight = max(0, n_obs) / (max(0, n_obs) + tau * tau)
    return tuple(
        round(prior_v + weight * (local_v - prior_v), 6)
        for local_v, prior_v in zip(local, prior, strict=True)
    )


def fit_affine(xs: tuple[float, ...], ys: tuple[float, ...]) -> GroupCalibration:
    """L2: least-squares affine calibration, identity when data is thin."""
    n = min(len(xs), len(ys))
    if n < MIN_OBS_FOR_CALIBRATION:
        return GroupCalibration(chat_key="", slope=1.0, offset=0.0, n_obs=n)
    mean_x = sum(xs[:n]) / n
    mean_y = sum(ys[:n]) / n
    var = sum((x - mean_x) ** 2 for x in xs[:n])
    if var <= 1e-9:
        return GroupCalibration(chat_key="", slope=1.0, offset=round(mean_y - mean_x, 4), n_obs=n)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs[:n], ys[:n], strict=True))
    slope = max(SLOPE_BOUNDS[0], min(SLOPE_BOUNDS[1], cov / var))
    offset = max(OFFSET_BOUNDS[0], min(OFFSET_BOUNDS[1], mean_y - slope * mean_x))
    return GroupCalibration(chat_key="", slope=round(slope, 4), offset=round(offset, 4), n_obs=n)


def apply_calibration(score: float, calib: GroupCalibration) -> float:
    """Map a raw depth score through the group's affine calibration."""
    if calib.n_obs < MIN_OBS_FOR_CALIBRATION:
        return score
    return round(calib.slope * score + calib.offset, 3)


class PageHinkley:
    """L4: CUSUM-style level-shift detector; returns True on the alarm sample."""

    def __init__(self, *, delta: float = 0.01, threshold: float = 0.5) -> None:
        self._delta = delta
        self._threshold = threshold
        self._n = 0
        self._mean = 0.0
        self._cum = 0.0
        self._min_cum = 0.0

    def update(self, value: float) -> bool:
        self._n += 1
        self._mean += (value - self._mean) / self._n
        self._cum += value - self._mean - self._delta
        self._min_cum = min(self._min_cum, self._cum)
        if self._cum - self._min_cum > self._threshold:
            self._cum = 0.0
            self._min_cum = 0.0
            return True
        return False
