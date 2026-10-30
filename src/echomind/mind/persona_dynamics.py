"""Stage 30 S30-3: bounded, slowly regressing personality dynamics.

param: convention:s30-dynamics - all three constants are engineering conventions chosen to
match the empirical claim that personality is stable and changes slowly (Roberts &
DelVecchio 2000, doi:10.1037//0033-2909.126.1.3). They are marked fit:pending and must be
calibrated against replay + operator anchors before being treated as final.
"""

from __future__ import annotations

DELTA_CLIP = 2.0
DAILY_CAP = 6.0
REGRESSION_PER_DAY = 0.01
MAX_CATCHUP_DAYS = 30.0


def clip_delta(delta: float) -> float:
    """Cap a single turn's change so one interaction cannot reshape her."""
    return max(-DELTA_CLIP, min(DELTA_CLIP, delta))


def slow_regression(value: float, baseline: float, days: float) -> float:
    """Return the regression delta for `days` elapsed (0 before a full day).

    1% per day toward the baseline → half-life ≈ 69 days, i.e. a trait that stopped being
    reinforced fades over months rather than within a session.
    """
    if days < 1.0:
        return 0.0
    horizon = min(days, MAX_CATCHUP_DAYS)
    remaining = float((1.0 - REGRESSION_PER_DAY) ** horizon)
    return (baseline - value) * (1.0 - remaining)


def budgeted_delta(raw: float, used_today: float, regression: float = 0.0) -> float:
    """Clip one turn, add slow regression, then spend whatever daily budget is left."""
    budget = max(0.0, DAILY_CAP - used_today)
    wanted = clip_delta(raw) + regression
    if wanted > 0:
        return float(min(wanted, budget))
    return float(max(wanted, -budget))
