"""M29 bond-depth model: earned closeness from reciprocated, diverse, responsive history.

Implements the composite predictor validated in Stage 29's literature review:
Berscheid et al. (1989) closeness triad (frequency / diversity / strength of influence),
Reis & Shaver (1988) perceived-responsiveness, Rusbult-style investment reciprocity,
with betrayal suppression and Beta-reputation trust with forgetting.

Provenance policy (PARAM-01): every module-level constant carries a `param:` tag.
- `src:<doi>`        — value or form taken from a published source;
- `convention:<id>`  — standard convention (e.g. RCI unit weighting, uniform Beta prior);
- `fit:<report-id>`  — empirically fitted on labelled data (report in docs/plans/).
Values tagged `fit:pending*` are PROVISIONAL hand-set defaults and must be replaced by
the Stage 29 fitting report before any behaviour is changed.
"""

from __future__ import annotations

import math

# RCI triad is scored as a unit-weighted composite in the source instrument.
W_FREQ = 1.00  # param: convention:rci-unit-weight
W_DIV = 1.20  # param: convention:rci-unit-weight
W_IMPACT = 1.10  # param: convention:rci-unit-weight
# Investment-model ordering (r=0.65 satisfaction > r=0.53 investment > r=-0.43 alternatives).
W_RECIP = 1.00  # param: src:10.1111/pere.12268
# Perceived responsiveness has no meta-analytic weight; must be fitted on our labels.
W_RESP = 1.40  # param: fit:pending-bond-depth
# Negativity bias is only qualitative in the literature; magnitude must be fitted.
W_BETRAY = 1.60  # param: fit:pending-bond-depth
# Sigmoid calibration is a design choice to be replaced by fitted logistic calibration.
BIAS = 2.60  # param: fit:pending-bond-depth
GAIN = 1.60  # param: fit:pending-bond-depth
# Saturation points should be the P90 of each feature in our own data.
FREQ_SATURATION = 500.0  # param: fit:pending-bond-depth
DIVERSITY_SATURATION = 12.0  # param: fit:pending-bond-depth
IMPACT_SATURATION = 45.0  # param: fit:pending-bond-depth
BETRAYAL_HALF_LIFE = 3.0  # param: fit:pending-bond-depth
DEPTH_CEILING = 0.97  # param: convention:soft-cap
# Care-weight blend between affinity/trust base and earned depth.
BASE_CARE_SHARE = 0.45  # param: fit:pending-bond-depth
DEPTH_CARE_SHARE = 0.55  # param: fit:pending-bond-depth
# Legacy mapping inherited from the pre-Stage-29 w_care formula.
AFFINITY_OFFSET = 38.0  # param: convention:legacy-w-care
AFFINITY_SPAN = 70.0  # param: convention:legacy-w-care
# Beta reputation conventionally starts from a uniform prior (alpha = beta = 1).
BETA_PRIOR = 2.0  # param: convention:beta-uniform-prior-pending


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def compute_bond_depth(
    *, msg_count: int, distinct_topics: int, responded_ratio: float,
    reciprocity: float, affect_impact: float, betrayal: int = 0,
) -> float:
    """Return earned relationship depth in [0, 100] (no configuration, no favourite)."""
    freq = _clamp01(math.log1p(max(0, msg_count)) / math.log1p(FREQ_SATURATION))
    diversity = _clamp01(max(0, distinct_topics) / DIVERSITY_SATURATION)
    responsivity = _clamp01(responded_ratio)
    reciprocal = _clamp01(reciprocity)
    impact = _clamp01(affect_impact / IMPACT_SATURATION)
    betrayed = _clamp01(1.0 - math.exp(-max(0, betrayal) / BETRAYAL_HALF_LIFE))
    weighted = (
        W_FREQ * freq + W_DIV * diversity + W_RESP * responsivity
        + W_RECIP * reciprocal + W_IMPACT * impact - W_BETRAY * betrayed
    )
    return round(100.0 * _sigmoid(GAIN * (weighted - BIAS)), 2)


def care_weight(affinity: float, trust: float, depth: float) -> float:
    """Continuous care weight w_care(u) in [0, 0.97] with no hardcoded owner privilege."""
    base = _clamp01((affinity - AFFINITY_OFFSET) / AFFINITY_SPAN) * _clamp01(trust)
    scaled = base * (BASE_CARE_SHARE + DEPTH_CARE_SHARE * _clamp01(depth / 100.0))
    return round(min(DEPTH_CEILING, max(0.0, scaled)), 3)


def beta_trust_update(
    pos: float, neg: float, *, positive: bool, weight: float = 1.0, forgetting: float = 0.995
) -> tuple[float, float, float]:
    """Fold one observation into Beta-reputation evidence and return the posterior mean."""
    decayed_pos = max(0.0, pos) * forgetting
    decayed_neg = max(0.0, neg) * forgetting
    if positive:
        decayed_pos += weight
    else:
        decayed_neg += weight
    trust = (decayed_pos + BETA_PRIOR) / (decayed_pos + decayed_neg + 2.0 * BETA_PRIOR)
    return round(decayed_pos, 4), round(decayed_neg, 4), round(trust, 4)
