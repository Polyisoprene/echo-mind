"""Stage 29 A3: owner identity must carry no emotional privilege (D1/D2)."""

from __future__ import annotations

import pytest

from echomind.domain.models import Percept, SocialBondProfile
from echomind.mind.drives import compute_aversion_susceptibility, compute_care_weight
from echomind.mind.memory_consolidator import _default_bond
from echomind.mind.subconscious_probe import SubconsciousChordResult, compute_chord_social_reward

OWNER = "10001001"


def _bond(uid: str, affinity: float, trust: float) -> SocialBondProfile:
    return SocialBondProfile(chat_key="g", user_id=uid, user_name=uid,
                             affinity_score=affinity, trust_score=trust)


def test_owner_gets_no_care_shortcut() -> None:
    ordinary = _bond(OWNER, 30.0, 0.75)
    assert compute_care_weight(OWNER, OWNER, ordinary) == pytest.approx(0.0, abs=1e-6)
    earned = _bond(OWNER, 95.0, 0.95).model_copy(update={"bond_depth": 80.0})
    assert compute_care_weight(OWNER, OWNER, earned) > 0.4


def test_owner_can_be_disliked() -> None:
    cold = _bond(OWNER, 20.0, 0.40)
    assert compute_aversion_susceptibility(OWNER, OWNER, cold) >= 0.40


def test_owner_reward_is_not_amplified() -> None:
    chord = SubconsciousChordResult(joy=3)
    assert compute_chord_social_reward(chord, is_owner=True) == compute_chord_social_reward(
        chord, is_owner=False
    )


def test_new_owner_bond_starts_like_anyone_else() -> None:
    percept = Percept(chat_key="g", scene="group", message_id="m", timestamp_ms=1,
                      sender_id=OWNER, sender_name="owner", text="hi")
    assert _default_bond("g", percept, True).affinity_score <= 100.0
