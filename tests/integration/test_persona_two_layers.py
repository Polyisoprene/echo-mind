"""E2 (C): persona is two layers — a slow trait baseline and a fast state offset.

Red first: a turn must not move the persisted trait baseline; it only moves the
fast state layer. The baseline moves once per day by at most TRAIT_DAILY_PUSH.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept, PlasticParamSpec, TurnOutcome
from echomind.mind.persona_dynamics import STATE_MAX_STEP
from echomind.mind.persona_state import decay_offset, effective_params, step_state


def _outcome(reward: float = 0.85) -> TurnOutcome:
    percept = Percept(
        chat_key="group:1",
        scene="group",
        message_id="m1",
        timestamp_ms=1_700_000_000_000,
        sender_id="10001",
        sender_name="小明",
        text="你今天真温柔",
        is_at_me=True,
    )
    return TurnOutcome(
        session_id="s1",
        chat_key="group:1",
        triggers=(percept,),
        sent_texts=("嘿嘿，被你发现了",),
        social_reward=reward,
    )


@pytest.mark.asyncio
async def test_turn_does_not_move_persona_baseline(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "layers.db")
    before = (await container.working_store.get_plastic_params())["persona_warmth"].value

    await container.cognitive_facade.on_turn_completed(_outcome())

    after = (await container.working_store.get_plastic_params())["persona_warmth"].value
    assert after == before, "a single turn must not rewrite the slow trait baseline"


def test_state_decays_with_the_configured_half_life() -> None:
    assert decay_offset(8.0, 45.0 * 60_000) == pytest.approx(4.0)


def test_state_step_is_bounded() -> None:
    offset, _ = step_state({}, "persona_warmth", 99.0, 1000)
    assert offset == STATE_MAX_STEP
    offset, _ = step_state({}, "persona_warmth", -99.0, 1000)
    assert offset == -STATE_MAX_STEP


def test_effective_params_overlay_state() -> None:
    params = {
        "persona_warmth": PlasticParamSpec(
            key="persona_warmth", value=65.0, min_bound=15.0, max_bound=98.0
        )
    }
    merged = effective_params(params, {"persona_warmth": (6.0, 0)}, 0)
    assert merged["persona_warmth"].value == pytest.approx(71.0)


@pytest.mark.asyncio
async def test_behaviour_params_use_the_two_layer_engine(tmp_path: Path) -> None:
    """The new engine covers behaviour keys too: state on the turn, baseline at settle."""
    import time

    container = await EchoMindContainer.create(db_path=tmp_path / "beh.db")
    baseline = (await container.working_store.get_plastic_params())["talkativeness"].value

    await container.cognitive_facade.on_turn_completed(_outcome(0.85))

    after_turn = (await container.working_store.get_plastic_params())["talkativeness"].value
    assert after_turn == baseline, "a turn must not move a behaviour baseline either"
    layers = container.persona_layers
    assert layers is not None
    state = await layers.load_state()
    assert state["talkativeness"][0] > 0, "the turn must land in the fast state"

    now_ms = int(time.time() * 1000)
    moved = await container.cognitive_facade._plasticity.settle_baseline(now_ms + 86_400_000)
    assert any(spec.key == "talkativeness" for spec in moved)
    settled = (await container.working_store.get_plastic_params())["talkativeness"].value
    assert settled > baseline
