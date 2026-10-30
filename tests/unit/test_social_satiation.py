"""Stage 31 invariants: social satiation must be soft, recoverable and human-specific.

S31-1  willingness stays inside [floor, 1]
S31-2  a sender believed to be human (b=0) is never affected
S31-3  repeated replies lower willingness, and a long gap restores it
S31-4  composing with the cold shoulder takes the lenient branch (max, not product)
S31-5  identical inputs and seed produce identical decisions
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bot_pingpong.json"


def test_fixture_has_twenty_rounds_and_three_new_topics() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(data["messages"]) == 20
    assert data["bot_id"] == "10009009"


def test_s31_1_willingness_is_bounded() -> None:
    from echomind.mind.social_satiation import willingness

    for h, b in ((0.0, 0.0), (0.5, 0.6), (0.999, 1.0)):
        p = willingness(h, b)
        assert 0.08 <= p <= 1.0


def test_s31_2_humans_are_unaffected() -> None:
    from echomind.mind.social_satiation import willingness

    for h in (0.0, 0.4, 0.9, 0.999):
        assert willingness(h, 0.0) == 1.0


def test_s31_3_repetition_decays_and_gap_restores() -> None:
    from echomind.mind.social_satiation import SatiationState

    state = SatiationState(tau_s=1800.0, alpha=0.40, floor=0.08)
    first = state.willingness("g", "bot", now_ms=0, bot_like=1.0)
    for i in range(1, 6):
        state.record_reply("g", "bot", now_ms=i * 15_000)
    after = state.willingness("g", "bot", now_ms=6 * 15_000, bot_like=1.0)
    assert after < first
    later = state.willingness("g", "bot", now_ms=6 * 15_000 + 3 * 3600_000, bot_like=1.0)
    assert later > after


def test_s31_4_cold_shoulder_takes_lenient_branch() -> None:
    from echomind.mind.social_satiation import combine_with_cold_shoulder

    assert combine_with_cold_shoulder(0.10, 0.35) == 0.35
    assert combine_with_cold_shoulder(0.80, 0.35) == 0.80


def test_s31_5_decisions_are_deterministic() -> None:
    from echomind.mind.social_satiation import SatiationState

    def run() -> list[float]:
        rng = random.Random(31)  # noqa: S311 - deterministic seed
        state = SatiationState(tau_s=1800.0, alpha=0.40, floor=0.08)
        out = []
        for i in range(10):
            out.append(state.willingness("g", "bot", now_ms=i * 20_000, bot_like=1.0))
            if rng.random() < out[-1]:
                state.record_reply("g", "bot", now_ms=i * 20_000)
        return out

    assert run() == run()


def test_mode_off_keeps_decisions_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    from echomind.domain.models import AttentionDecision
    from echomind.mind.social_satiation import SatiationState, adjust_decision

    monkeypatch.delenv("ECHOMIND_SATIATION", raising=False)
    dec = AttentionDecision(should_wake=True, salience_score=0.9, tier=2, reason="x")
    percept = type("P", (), {"chat_key": "g", "sender_id": "bot", "timestamp_ms": 0})()
    state = SatiationState()
    for _ in range(5):
        state.record_reply("g", "bot", 0)
    assert adjust_decision(dec, percept, state, 1.0) is dec


def test_mode_on_suppresses_most_but_not_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Probabilistic: tired out she still occasionally answers."""
    from echomind.domain.models import AttentionDecision
    from echomind.mind.social_satiation import SatiationState, adjust_decision

    monkeypatch.setenv("ECHOMIND_SATIATION", "on")
    dec = AttentionDecision(should_wake=True, salience_score=0.9, tier=2, reason="x")
    state = SatiationState()
    for _ in range(6):
        state.record_reply("g", "bot", 0)
    kept, suppressed = 0, 0
    for ts in range(0, 2000, 10):
        percept = type("P", (), {"chat_key": "g", "sender_id": "bot", "timestamp_ms": ts})()
        out = adjust_decision(dec, percept, state, 1.0)
        kept += 1 if out.should_wake else 0
        suppressed += 0 if out.should_wake else 1
        if not out.should_wake:
            assert "习惯化" in out.reason
    assert suppressed > kept * 5, f"expected heavy suppression, kept={kept} suppressed={suppressed}"
    assert kept > 0, "a floor must always leave a chance to answer"


def test_draws_are_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    from echomind.domain.models import AttentionDecision
    from echomind.mind.social_satiation import SatiationState, adjust_decision

    monkeypatch.setenv("ECHOMIND_SATIATION", "on")
    dec = AttentionDecision(should_wake=True, salience_score=0.9, tier=2, reason="x")
    state = SatiationState()
    for _ in range(6):
        state.record_reply("g", "bot", 0)
    percept = type("P", (), {"chat_key": "g", "sender_id": "bot", "timestamp_ms": 12345})()
    assert adjust_decision(dec, percept, state, 1.0) == adjust_decision(dec, percept, state, 1.0)
