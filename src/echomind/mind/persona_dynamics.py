"""E2: two-layer persona dynamics — a slow trait baseline and a fast state layer.

The slow layer may move TRAIT_DAILY_PUSH per day (derived from a 4-point annual budget
and a 12-point maximum deviation) and regresses at TRAIT_REGRESSION_PER_DAY. The fast
layer lives in `mind/persona_state.py` and is bounded separately.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping

from echomind.domain.models import PlasticParamSpec

DELTA_CLIP = 2.0
DAILY_CAP = 6.0
MAX_CATCHUP_DAYS = 30.0

# param: convention:persona-annual-budget - product decision (2026-10-31): the slow
# trait layer may move at most 4 points in year one, band 3-6. Literature order of
# magnitude for adult mean-level change is 0.3-0.9 points/year (Roberts, Walton &
# Viechtbauer 2006, Psychological Bulletin 132(1):1-25), so this is a deliberate
# 5-15x acceleration for a young virtual character; it is NOT a human-like rate.
TRAIT_ANNUAL_BUDGET = 4.0
# param: convention:persona-max-deviation - asymptotic distance from the set point
# (about 1/7 of the 85-point usable range). Regression balances the daily push here.
TRAIT_MAX_DEVIATION = 12.0

# Derived, so the pair can never drift apart: solve X = M*(1-exp(-365*D/M)) for D.
TRAIT_DAILY_PUSH = (
    -math.log(1.0 - TRAIT_ANNUAL_BUDGET / TRAIT_MAX_DEVIATION) * TRAIT_MAX_DEVIATION / 365.0
)
TRAIT_REGRESSION_PER_DAY = TRAIT_DAILY_PUSH / TRAIT_MAX_DEVIATION
# Slow trait regression is the derived rate, not the old 1%/day state-level decay.
REGRESSION_PER_DAY = TRAIT_REGRESSION_PER_DAY

# param: fit:pending - fast state layer, calibrated by the sensitivity audit (E1-013).
STATE_MAX_ABS = 10.0
STATE_MAX_STEP = 4.0
STATE_HALF_LIFE_MIN = 45.0


def clip_delta(delta: float) -> float:
    """Cap a single turn's change so one interaction cannot reshape her."""
    return max(-DELTA_CLIP, min(DELTA_CLIP, delta))


def slow_regression(value: float, baseline: float, days: float) -> float:
    """Return the regression delta for `days` elapsed (0 before a full day).

    TRAIT_REGRESSION_PER_DAY (~0.11%/day) toward the baseline → half-life ≈ 624 days,
    i.e. a trait that stopped being reinforced fades over years rather than weeks.
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


async def capped_manual_delta(
    store: object, key: str, delta: float
) -> tuple[float, float]:
    """Apply the daily cap to a console edit; returns (applied, remaining_budget)."""
    now_ms = int(time.time() * 1000)
    usage = getattr(store, "persona_day_usage", None)
    used = await usage(key, now_ms - 86_400_000) if callable(usage) else 0.0
    applied = budgeted_delta(delta, used)
    return applied, round(max(0.0, DAILY_CAP - used - abs(applied)), 2)


def param_value(params: Mapping[str, PlasticParamSpec], key: str, default: float) -> float:
    """Read a plastic parameter with a fallback (None-safe)."""
    spec = params.get(key)
    return spec.value if spec is not None else default
