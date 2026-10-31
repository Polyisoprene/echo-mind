"""P6e finding: soothing must fire on reunion, not on every ordinary turn."""

from __future__ import annotations

from echomind.domain.models import (
    AffectiveVector,
    Percept,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.mind.drives import REUNION_GAP_MIN, apply_turn_affect_and_drives
from echomind.mind.subconscious_probe import SubconsciousChordResult

NOW_MS = 1_700_000_000_000
NEUTRAL = SubconsciousChordResult()


def _bond(last_seen_ms: int) -> SocialBondProfile:
    return SocialBondProfile(
        chat_key="g",
        user_id="u",
        user_name="u",
        affinity_score=80.0,
        trust_score=0.9,
        bond_depth=50.0,
        last_seen_ms=last_seen_ms,
    )


def _step(gap_min: float) -> tuple[float, float]:
    percept = Percept(
        chat_key="g", scene="group", message_id="m", timestamp_ms=NOW_MS,
        sender_id="u", sender_name="u", text="在吗",
    )
    before = WorkingSnapshot(
        scope_key="global",
        affect=AffectiveVector(
            valence=62.0, energy=75.0, jealousy=0.0, shyness=20.0, irritation=0.0
        ),
    )
    after = apply_turn_affect_and_drives(
        before, (percept,), (), bonds_map={"u": _bond(NOW_MS - int(gap_min * 60_000))},
        chord=NEUTRAL,
    )
    return (
        after.affect.valence - before.affect.valence,
        after.drives.attachment - before.drives.attachment,
    )


def test_ordinary_turn_does_not_soothe() -> None:
    valence, attachment = _step(1.0)
    assert valence < 2.0, "a neutral follow-up must not be a reunion"
    assert attachment > 0.0, "ordinary positive contact should still build attachment"


def test_reunion_soothes_and_lifts_valence() -> None:
    ordinary_valence, _ = _step(1.0)
    reunion_valence, reunion_attachment = _step(REUNION_GAP_MIN * 2)
    assert reunion_valence > ordinary_valence
    assert reunion_attachment < 0.0, "soothing should discharge attachment pressure"


def test_threshold_boundary() -> None:
    below, _ = _step(REUNION_GAP_MIN - 1.0)
    above, _ = _step(REUNION_GAP_MIN + 1.0)
    assert above > below
