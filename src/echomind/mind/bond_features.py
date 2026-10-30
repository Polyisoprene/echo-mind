"""Derive the six bond-depth features from persisted counters (pure, no I/O)."""

from __future__ import annotations

from echomind.domain.bond_stats import BondDepthStats, BondFeatures
from echomind.mind.bond_depth import (
    BETRAYAL_HALF_LIFE,
    DIVERSITY_SATURATION,
    FREQ_SATURATION,
    IMPACT_SATURATION,
    compute_bond_depth,
)


def features_from_stats(stats: BondDepthStats) -> BondFeatures:
    """Normalize raw counters into the six [0, 1] features consumed by the model."""
    import math

    freq = min(1.0, math.log1p(max(0, stats.msgs)) / math.log1p(FREQ_SATURATION))
    diversity = min(1.0, max(0, stats.sessions) / DIVERSITY_SATURATION)
    responsivity = min(1.0, stats.responded_to_her / max(1, stats.her_msgs))
    denom = stats.replies_to_them + stats.msgs + 1
    reciprocity = min(1.0, 2.0 * min(stats.replies_to_them, stats.msgs) / denom)
    impact = min(1.0, (stats.impact_sum / max(1, stats.impact_n)) / IMPACT_SATURATION)
    betrayal = 1.0 - math.exp(-max(0, stats.betrayals) / BETRAYAL_HALF_LIFE)
    return BondFeatures(
        frequency=round(freq, 4), diversity=round(diversity, 4),
        responsivity=round(min(1.0, responsivity), 4), reciprocity=round(reciprocity, 4),
        impact=round(impact, 4), betrayal=round(betrayal, 4),
    )


def depth_from_stats(stats: BondDepthStats) -> float:
    """Compute earned bond depth directly from persisted counters."""
    f = features_from_stats(stats)
    return compute_bond_depth(
        msg_count=stats.msgs,
        distinct_topics=round(f.diversity * DIVERSITY_SATURATION),
        responded_ratio=f.responsivity,
        reciprocity=f.reciprocity,
        affect_impact=f.impact * IMPACT_SATURATION,
        betrayal=stats.betrayals,
    )
