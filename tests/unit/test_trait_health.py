"""Health states distinguish waiting for traffic from a broken shadow write."""

from __future__ import annotations

from echomind.mind.trait_health import TraitHealth


def test_no_active_trait() -> None:
    assert TraitHealth(0, 0, 0, 0, 0).status == "no_active"


def test_active_but_no_turn_yet() -> None:
    assert TraitHealth(1, 0, 0, 0, 10).status == "waiting_turn"


def test_shadow_exists_but_has_no_trait() -> None:
    assert TraitHealth(1, 1, 0, 0, 10).status == "shadow_missing_trait"


def test_shadow_has_trait_but_no_causal_link() -> None:
    assert TraitHealth(1, 1, 1, 0, 10).status == "no_causal_links"


def test_healthy() -> None:
    assert TraitHealth(1, 1, 1, 1, 10).status == "ok"
