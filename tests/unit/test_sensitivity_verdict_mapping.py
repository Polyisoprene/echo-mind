"""P6e regression: the judge's A/B must map back to the right level."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

ROOT = Path(__file__).resolve().parents[2]


def _load_runner() -> ModuleType:
    path = ROOT / "scripts" / "persona_sensitivity.py"
    spec = importlib.util.spec_from_file_location("persona_sensitivity", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_judge_labels_map_to_levels() -> None:
    module = _load_runner()
    winner_level = cast(Callable[..., str], module.__dict__["_winner_level"])
    assert winner_level("A", swapped=False) == "low"
    assert winner_level("B", swapped=False) == "high"
    assert winner_level("A", swapped=True) == "high"
    assert winner_level("B", swapped=True) == "low"
    assert winner_level("tie", swapped=False) == "tie"
