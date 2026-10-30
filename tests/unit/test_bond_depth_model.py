"""Stage 29 RGR: bond depth must be earned from reciprocated, diverse, responsive history."""

from __future__ import annotations

import pytest

from echomind.mind.bond_depth import beta_trust_update, care_weight, compute_bond_depth


def test_cold_start_has_no_favourite() -> None:
    depth = compute_bond_depth(
        msg_count=0, distinct_topics=0, responded_ratio=0.0,
        reciprocity=0.0, affect_impact=0.0, betrayal=0,
    )
    assert depth <= 3.0, f"a stranger must not start deep, got {depth}"


def test_praise_only_does_not_create_a_favourite() -> None:
    praiser = compute_bond_depth(
        msg_count=400, distinct_topics=1, responded_ratio=0.05,
        reciprocity=0.1, affect_impact=0.2, betrayal=0,
    )
    friend = compute_bond_depth(
        msg_count=180, distinct_topics=30, responded_ratio=0.6,
        reciprocity=0.8, affect_impact=0.5, betrayal=0,
    )
    assert praiser < 20.0, f"love bombing must not buy depth, got {praiser}"
    assert friend > 55.0, f"reciprocal diverse history must earn depth, got {friend}"
    assert friend - praiser > 40.0


def test_betrayal_suppresses_depth() -> None:
    clean = compute_bond_depth(
        msg_count=180, distinct_topics=30, responded_ratio=0.6,
        reciprocity=0.8, affect_impact=0.5, betrayal=0,
    )
    betrayed = compute_bond_depth(
        msg_count=180, distinct_topics=30, responded_ratio=0.6,
        reciprocity=0.8, affect_impact=0.5, betrayal=3,
    )
    assert clean - betrayed >= 15.0, f"betrayal must cost depth ({clean} -> {betrayed})"


def test_depth_is_monotonic_in_history() -> None:
    values = [
        compute_bond_depth(
            msg_count=n, distinct_topics=4, responded_ratio=0.5,
            reciprocity=0.7, affect_impact=0.4, betrayal=0,
        )
        for n in (0, 20, 100, 400)
    ]
    assert values == sorted(values)


def test_care_weight_removes_the_owner_privilege() -> None:
    stranger = care_weight(30.0, 0.75, 0.0)
    deep = care_weight(81.66, 0.85, 80.0)
    shallow = care_weight(81.66, 0.85, 0.0)
    assert stranger == pytest.approx(0.0, abs=1e-6)
    assert deep > shallow, "depth must add care beyond raw affinity"
    assert deep <= 0.97
    assert care_weight(500.0, 1.0, 100.0) > 0.9


def test_beta_trust_accumulates_and_forgets() -> None:
    pos, neg = 0.0, 0.0  # evidence starts empty; the Beta prior lives inside the model
    for _ in range(10):
        pos, neg, trust = beta_trust_update(pos, neg, positive=True)
    assert trust > 0.8, f"positive history must raise trust, got {trust}"
    for _ in range(3):
        pos, neg, trust = beta_trust_update(pos, neg, positive=False)
    assert trust < 0.8, f"betrayal must lower trust, got {trust}"
    decayed_pos, _, _ = beta_trust_update(10_000.0, 2.0, positive=True)
    assert decayed_pos < 10_050.0, "evidence must be forgettable over time"
