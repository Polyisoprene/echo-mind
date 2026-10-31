"""P0: one profile per person; venue affinity is the only thing that varies."""

from __future__ import annotations

import pytest

from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.person_level import (
    aggregate_stats,
    build_profiles,
    care_weight_from_profile,
    stance_from_profile,
)


def _bond(
    chat: str, uid: str, *, aff: float, trust: float, depth: float, msgs: int
) -> SocialBondProfile:
    return SocialBondProfile(
        chat_key=chat, user_id=uid, user_name=uid,
        affinity_score=aff, trust_score=trust, bond_depth=depth, msg_count=msgs,
    )


def _stats(chat: str, uid: str, msgs: int, sessions: int, impact_n: int = 5) -> BondDepthStats:
    return BondDepthStats(
        chat_key=chat, user_id=uid, msgs=msgs, sessions=sessions,
        responded_to_her=msgs, her_msgs=msgs // 3, replies_to_them=msgs // 3,
        impact_sum=0.5 * impact_n, impact_n=impact_n,
    )


def test_same_person_gets_one_profile_and_one_temperature() -> None:
    bonds = [
        _bond("group:1", "owner", aff=54.5, trust=0.61, depth=71.0, msgs=680),
        _bond("private:owner", "owner", aff=32.1, trust=0.78, depth=50.7, msgs=312),
    ]
    stats = [_stats("group:1", "owner", 368, 49, 23), _stats("private:owner", "owner", 28, 12, 6)]
    profile = build_profiles(bonds, stats)["owner"]

    assert profile.trust == pytest.approx(0.663, abs=0.002)
    assert profile.depth_raw > 0
    group_stance = stance_from_profile(bonds[0], profile)
    private_stance = stance_from_profile(bonds[1], profile)
    assert group_stance[0] == private_stance[0], "warmth must not depend on the room"
    assert group_stance[1] == private_stance[1], "patience must not depend on the room"
    assert group_stance[2] > private_stance[2], "play stays venue-specific"
    assert care_weight_from_profile(profile) > 0, "person-level affinity avoids the cutoff"


def test_bottom_of_group_is_not_zeroed() -> None:
    """The within-group rank blend zeroes the least active member; the profile must not."""
    bonds = [
        _bond("g", "low", aff=40.0, trust=0.6, depth=0.0, msgs=10),
        _bond("g", "mid", aff=45.0, trust=0.6, depth=30.0, msgs=60),
        _bond("g", "high", aff=60.0, trust=0.7, depth=70.0, msgs=500),
    ]
    stats = [_stats("g", "low", 30, 4), _stats("g", "mid", 80, 10), _stats("g", "high", 500, 60)]
    profiles = build_profiles(bonds, stats)
    assert profiles["low"].depth_raw > 10
    assert profiles["low"].depth_percentile >= 0
    assert profiles["high"].depth_percentile > profiles["low"].depth_percentile


def test_aggregate_stats_sums_venues() -> None:
    merged = aggregate_stats("u", [_stats("g", "u", 100, 10, 4), _stats("p", "u", 20, 2, 1)])
    assert merged is not None
    assert merged.msgs == 120
    assert merged.sessions == 12
    assert merged.impact_n == 5
