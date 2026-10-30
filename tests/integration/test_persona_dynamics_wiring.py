"""Stage 30 S30-3: the live plasticity path honours clip, daily cap and slow regression."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.persona_dynamics import slow_regression
from echomind.mind.plasticity import PARAM_BASELINES, NeuroplasticityEngine


def _outcome(reward: float) -> TurnOutcome:
    percept = Percept(chat_key="g", scene="group", message_id="m", timestamp_ms=1,
                      sender_id="u", sender_name="u", text="hi")
    return TurnOutcome(session_id="s", chat_key="g", triggers=(percept,), social_reward=reward)


async def test_daily_cap_holds_through_the_engine(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "dyn.db")
    await db.initialize()
    store = SqliteWorkingStateStore(db)
    await store.ensure_default_params()
    engine = NeuroplasticityEngine(store)
    for _ in range(50):
        await engine.adapt_from_outcome(_outcome(0.85))
    params = await store.get_plastic_params()
    baseline = PARAM_BASELINES["persona_warmth"]
    assert params["persona_warmth"].value - baseline <= 6.5, "daily cap not enforced"


def test_slow_regression_has_a_monthly_half_life() -> None:
    ten_days = slow_regression(90.0, 60.0, 10.0)
    seventy_days = slow_regression(90.0, 60.0, 70.0)
    # 1%/day with a 30-day catch-up cap: ten days ≈ 2.9, seventy days ≈ 7.8 of a 30 gap.
    assert 2.0 < abs(ten_days) < abs(seventy_days) < 10.0
    assert 7.0 < abs(seventy_days) < 9.0, "a long absence must only partially regress"
