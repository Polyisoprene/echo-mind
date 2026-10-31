"""Person-level relationship profile: one trust/depth per person; affinity stays per venue.

The live model stores one bond per (chat_key, user_id) and derives stance from a
within-group rank-blended depth, so the same person is treated differently depending
on who else shares the room. This module is the pure core of the fix: it aggregates
the venue rows into one profile per person, and leaves venue affinity to the caller.

No I/O. Wiring lands in later P0 steps.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.bond_adapt import percentile_rank
from echomind.mind.bond_depth import care_weight
from echomind.mind.bond_features import depth_from_stats


@dataclass(frozen=True)
class PersonProfile:
    """One person, independent of which room they are in."""

    person_id: str
    trust: float
    affinity: float
    depth_raw: float
    depth_percentile: float


def _weighted_mean(values: Iterable[float], weights: Iterable[int]) -> float:
    pairs = tuple(zip(values, weights, strict=True))
    total = sum(w for _v, w in pairs)
    if not total:
        return 0.0
    return sum(v * w for v, w in pairs) / total


def aggregate_stats(person_id: str, rows: Iterable[BondDepthStats]) -> BondDepthStats | None:
    """Sum the per-venue counters into one person-level counter set."""
    rows = tuple(rows)
    if not rows:
        return None
    return BondDepthStats(
        chat_key="person",
        user_id=person_id,
        msgs=sum(r.msgs for r in rows),
        sessions=sum(r.sessions for r in rows),
        responded_to_her=sum(r.responded_to_her for r in rows),
        her_msgs=sum(r.her_msgs for r in rows),
        replies_to_them=sum(r.replies_to_them for r in rows),
        impact_sum=sum(r.impact_sum for r in rows),
        impact_n=sum(r.impact_n for r in rows),
        betrayals=sum(r.betrayals for r in rows),
    )


def build_profiles(
    bonds: Iterable[SocialBondProfile], stats: Iterable[BondDepthStats]
) -> dict[str, PersonProfile]:
    """Collapse venue bonds into person profiles, with a global depth percentile."""
    by_person: dict[str, list[SocialBondProfile]] = defaultdict(list)
    for bond in bonds:
        by_person[bond.user_id].append(bond)
    stats_by_person: dict[str, list[BondDepthStats]] = defaultdict(list)
    for row in stats:
        stats_by_person[row.user_id].append(row)

    raw_depth: dict[str, float] = {}
    for person_id in by_person:
        aggregated = aggregate_stats(person_id, stats_by_person.get(person_id, ()))
        raw_depth[person_id] = depth_from_stats(aggregated) if aggregated else 0.0
    ids = tuple(raw_depth)
    percentiles = dict(
        zip(ids, percentile_rank(tuple(raw_depth[i] for i in ids)), strict=True)
    )

    profiles: dict[str, PersonProfile] = {}
    for person_id, rows in by_person.items():
        weights = tuple(max(1, bond.msg_count) for bond in rows)
        profiles[person_id] = PersonProfile(
            person_id=person_id,
            trust=round(_weighted_mean((b.trust_score for b in rows), weights), 4),
            affinity=round(_weighted_mean((b.affinity_score for b in rows), weights), 4),
            depth_raw=round(raw_depth[person_id], 2),
            depth_percentile=round(percentiles[person_id] * 100.0, 2),
        )
    return profiles


def stance_from_profile(
    bond: SocialBondProfile, profile: PersonProfile | None
) -> tuple[float, float, float]:
    """(warmth, patience, play): warmth/patience from the person, play from the venue."""
    depth = profile.depth_percentile if profile is not None else bond.bond_depth
    trust = profile.trust if profile is not None else bond.trust_score
    warmth = math.tanh(depth / 100.0 * 1.6)
    patience = math.tanh((trust - 0.5) * 2.0)
    play = math.tanh((bond.affinity_score - 50.0) / 50.0)
    return (warmth, patience, play)


def care_weight_from_profile(profile: PersonProfile) -> float:
    """Care weight with person-level affinity/trust/depth (avoids the venue cutoff bug)."""
    return care_weight(profile.affinity, profile.trust, profile.depth_percentile)


__all__ = [
    "PersonProfile",
    "aggregate_stats",
    "build_profiles",
    "care_weight_from_profile",
    "stance_from_profile",
]
