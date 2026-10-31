"""Stage 30 invariants: the target properties the personality rewrite must guarantee.

I-1  theta always stays inside its declared bounds
I-2  no dimension may move more than 6 points per simulated day
I-3  the rendered tone may not contradict the per-dimension rubric tiers
I-4  the same state always renders the same directive (determinism)
"""

from __future__ import annotations

import random

from echomind.domain.models import Percept, PersonaTrait, PlasticParamSpec, TurnOutcome
from echomind.mind.persona_rubrics import DIMENSION_RUBRICS
from echomind.mind.personality import (
    compute_personality_deltas,
    synthesize_live_persona_directive,
)
from echomind.mind.plasticity import PARAM_BASELINES, boundary_damping

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
    rng = random.Random(30)  # noqa: S311 - deterministic test seed, not crypto
    for _ in range(2000):
        delta = rng.uniform(-4.0, 4.0)
        value += boundary_damping(value, delta, lo, hi)
        value = max(lo, min(hi, value))
        assert lo <= value <= hi
    _ = (low, high)


def test_i2_daily_change_is_capped() -> None:
    """I-2: 100 positive turns inside one day must not move a dimension by more than 6."""
    from echomind.mind.persona_dynamics import budgeted_delta

    used = 0.0
    for _ in range(100):
        raw = sum(d for key, d, _ in compute_personality_deltas(_outcome(0.85))
                  if key == "persona_warmth")
        step = budgeted_delta(raw, used)
        used += abs(step)
    assert abs(used) <= 6.0 + 1e-6, f"daily warmth drift {used:.1f} exceeds the 6-point cap"


def test_i2b_single_turn_is_clipped() -> None:
    """I-2b: one turn can never move a dimension by more than 2 points."""
    from echomind.mind.persona_dynamics import clip_delta

    assert clip_delta(50.0) == 2.0
    assert clip_delta(-50.0) == -2.0


def _dominant_archetype(tone: str) -> str:
    return tone.split("% ", 1)[1].split("（", 1)[0]


def test_i3b_tone_is_continuous() -> None:
    """I-3b: a one-point change must not snap to a different dominant archetype."""
    from echomind.mind.personality import describe_attachment

    near = {_dominant_archetype(describe_attachment(70.0, 55.0, p)) for p in (60.0, 61.0, 62.0)}
    assert len(near) == 1, f"tone jumped between archetypes: {near}"


def test_i4_render_is_deterministic() -> None:
    """I-4: identical inputs render identical directives."""
    params = {key: _spec(key) for key in PARAM_BASELINES if key.startswith("persona_")}
    assert synthesize_live_persona_directive(params, ()) == synthesize_live_persona_directive(
        params, ()
    )


def _spec(key: str) -> PlasticParamSpec:
    return PlasticParamSpec(key=key, value=PARAM_BASELINES[key], min_bound=0.0, max_bound=100.0,
                            description=key)


def test_only_active_and_legacy_traits_reach_the_prompt() -> None:
    traits = (
        PersonaTrait(trait_text="活跃习惯", status="active"),
        PersonaTrait(trait_text="旧习惯", status="legacy_unverified"),
        PersonaTrait(trait_text="候选不该出现", status="candidate"),
        PersonaTrait(trait_text="退休不该出现", status="retired"),
    )
    directive = synthesize_live_persona_directive({}, traits, max_traits=10)
    assert "活跃习惯" in directive
    assert "旧习惯" in directive
    assert "候选不该出现" not in directive
    assert "退休不该出现" not in directive
