"""P6e: repeat aggregation must use a t-interval, not the normal approximation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    path = ROOT / "scripts" / "persona_sensitivity.py"
    spec = importlib.util.spec_from_file_location("persona_sensitivity", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runs() -> list[dict[str, Any]]:
    return [
        {"accuracy": 0.6, "ci95": [0.0, 1.0], "passes_chance": True},
        {"accuracy": 0.8, "ci95": [0.0, 1.0], "passes_chance": True},
        {"accuracy": 0.7, "ci95": [0.0, 1.0], "passes_chance": True},
    ]


def test_single_run_is_returned_unchanged() -> None:
    aggregate = cast(Any, _load().__dict__["_aggregate"])
    runs = _runs()[:1]
    assert aggregate(runs, 1)["accuracy"] == 0.6


def test_three_runs_use_the_t_interval() -> None:
    aggregate = cast(Any, _load().__dict__["_aggregate"])
    merged = aggregate(_runs(), 3)
    assert merged["accuracy"] == pytest.approx(0.7)
    assert merged["accuracy_sd"] == pytest.approx(0.1)
    # t(2)=4.303 * 0.1/sqrt(3) = 0.248 -> lower ~0.452, so it must NOT pass.
    assert merged["ci95"][0] < 0.5
    assert merged["passes_chance"] is False
