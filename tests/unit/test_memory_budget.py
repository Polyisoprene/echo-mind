"""Stage 44: consolidation token budget is configurable and clamped."""

from __future__ import annotations

from echomind.mind.memory_budget import (
    DEFAULT_CONSOLIDATION_BUDGET,
    consolidation_budget,
    set_consolidation_budget,
)


def test_default_budget() -> None:
    set_consolidation_budget(900)
    assert consolidation_budget() == 900


def test_budget_clamps_and_falls_back() -> None:
    set_consolidation_budget(10)
    assert consolidation_budget() == 200
    set_consolidation_budget("abc")
    assert consolidation_budget() == DEFAULT_CONSOLIDATION_BUDGET
