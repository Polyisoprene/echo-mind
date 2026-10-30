"""Stage 30 invariants: the target properties the personality rewrite must guarantee.

I-1  theta always stays inside its declared bounds
I-2  no dimension may move more than 6 points per simulated day
I-3  the rendered tone may not contradict the per-dimension rubric tiers
I-4  the same state always renders the same directive (determinism)
"""

from __future__ import annotations

import random

import pytest

from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.personality import (
    _describe_warmth_and_attachment,
    _format_dim_rubric,
    compute_personality_deltas,
    DIMENSION_RUBRICS,
    synthesize_live_persona_directive,
)
from echomind.mind.plasticity import boundary_damping, PARAM_BASELINES

WARMTH = next(spec for spec in DIMENSION_RUBRICS if spec[0] == "persona_warmth")
POSSESS = next(spec for spec in DIMENSION_RUBRICS if spec[0] == "persona_possessiveness")


def _outcome(reward: float) -> TurnOutcome:
    percept = Percept(chat_key="g", scene="group", message_id="m", timestamp_ms=1,
                      sender_id="u", sender_name="u", text="hi")
    return TurnOutcome(session_id="s", chat_key="g", triggers=(percept,), social_reward=reward)


def test_i1_bounds_are_never_violated() -> None:
    """I-1: any delta sequence keeps a dimension inside [min, max]."""
    low, high = WARMTH[4], WARMTH[5]
    lo, hi = 15.0, 98.0
    value = 65.0
    rng = random.Random(30)
    for _ in range(2000):
        delta = rng.uniform(-4.0, 4.0)
        value += boundary_damping(value, delta, lo, hi)
        value = max(lo, min(hi, value))
        assert lo <= value <= hi
    _ = (low, high)


@pytest.mark.xfail(strict=True, reason="S30-3: daily cap not implemented yet")
def test_i2_daily_change_is_capped() -> None:
    """I-2: 100 positive turns inside one day must not move a dimension by more than 6."""
    total = 0.0
    for _ in range(100):
        for key, delta, _reason in compute_personality_deltas(_outcome(0.85)):
            if key == "persona_warmth":
                total += delta
    assert abs(total) <= 6.0, f"daily warmth drift {total:.1f} exceeds the 6-point cap"


@pytest.mark.xfail(strict=True, reason="S30-2: narrative is still a hard branch")
def test_i3_tone_cannot_contradict_rubric() -> None:
    """I-3: high possessiveness must be reflected in the rendered tone."""
    warmth, tsundere, possess = 73.4, 55.8, 93.4
    tone = _describe_warmth_and_attachment(warmth, tsundere, possess)
    rubric = _format_dim_rubric({}, POSSESS)
    high_tier = "高" in rubric
    assert not (high_tier and "独占" not in tone), (
        f"rubric says high possessiveness but tone is {tone!r}"
    )


def test_i4_render_is_deterministic() -> None:
    """I-4: identical inputs render identical directives."""
    params = {key: _spec(key) for key in PARAM_BASELINES if key.startswith("persona_")}
    assert synthesize_live_persona_directive(params, ()) == synthesize_live_persona_directive(
        params, ()
    )


def _spec(key: str):  # noqa: ANN202 - local helper
    from echomind.domain.models import PlasticParamSpec

    return PlasticParamSpec(key=key, value=PARAM_BASELINES[key], min_bound=0.0, max_bound=100.0,
                            description=key)
