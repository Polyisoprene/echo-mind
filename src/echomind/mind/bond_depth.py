"""M29 bond-depth model: earned closeness from reciprocated, diverse, responsive history.

Implements the composite predictor validated in Stage 29's literature review:
Berscheid et al. (1989) closeness triad (frequency / diversity / strength of influence),
Reis & Shaver (1988) perceived-responsiveness, Rusbult-style investment reciprocity,
with betrayal suppression and Beta-reputation trust with forgetting.
"""

from __future__ import annotations

import math

W_FREQ = 1.00
W_DIV = 1.20
W_RESP = 1.40
W_RECIP = 1.00
W_IMPACT = 1.10
W_BETRAY = 1.60
BIAS = 2.60
GAIN = 1.60
FREQ_SATURATION = 500.0
DIVERSITY_SATURATION = 12.0
IMPACT_SATURATION = 45.0
BETRAYAL_HALF_LIFE = 3.0
DEPTH_CEILING = 0.97
BASE_CARE_SHARE = 0.45
DEPTH_CARE_SHARE = 0.55
AFFINITY_OFFSET = 38.0
AFFINITY_SPAN = 70.0
BETA_PRIOR = 2.0


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
