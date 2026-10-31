"""E2 (C): turns move the fast state; only the daily settlement moves the baseline."""

from __future__ import annotations

import time
from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.persona_layer_repo import SqlitePersonaLayerStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.persona_dynamics import (
    STATE_MAX_ABS,
    TRAIT_DAILY_PUSH,
    slow_regression,
)
from echomind.mind.plasticity import PARAM_BASELINES, NeuroplasticityEngine


def _outcome(reward: float) -> TurnOutcome:
    percept = Percept(chat_key="g", scene="group", message_id="m", timestamp_ms=1,
                      sender_id="u", sender_name="u", text="hi")
    return TurnOutcome(session_id="s", chat_key="g", triggers=(percept,), social_reward=reward)


async def test_turns_move_state_and_daily_settlement_bounds_the_baseline(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "dyn.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    await store.ensure_default_params()
    layers = SqlitePersonaLayerStore(db)
    await layers.ensure_schema()
    engine = NeuroplasticityEngine(store, layers)

    for _ in range(50):
        await engine.adapt_from_outcome(_outcome(0.85))

    baseline = PARAM_BASELINES["persona_warmth"]
    params = await store.get_plastic_params()
    assert params["persona_warmth"].value == baseline, "turns must not rewrite the baseline"
    state = await layers.load_state()
    assert 0 < state["persona_warmth"][0] <= STATE_MAX_ABS

    future = int(time.time() * 1000) + 86_400_000
    await engine.settle_baseline(future)
    after = (await store.get_plastic_params())["persona_warmth"].value
    assert 0 < after - baseline <= TRAIT_DAILY_PUSH + 1e-6


def test_daily_regression_halves_in_about_624_days() -> None:
    value = 100.0
    for _ in range(624):
        value += slow_regression(value, 0.0, 1.0)
    assert 45.0 < value < 55.0, "one settlement per day should halve a gap in ~624 days"
