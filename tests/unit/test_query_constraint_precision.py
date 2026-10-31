"""Constraint cues must fire only on the categories they are designed for."""

from __future__ import annotations

import json
from pathlib import Path

from echomind.mind.ranker_fusion import _DIRECTION, _temporal_mode

DATA = (
    Path(__file__).resolve().parents[2]
    / "eval" / "datasets" / "persona_memory_v1" / "scenarios.json"
)


def test_constraints_do_not_fire_outside_role_and_temporal() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for scenario in data["scenarios"]:
        query = scenario.get("query", "")
        if not query:
            continue
        temporal = _temporal_mode(query) is not None
        directional = any(cue in query for cue in _DIRECTION)
        assert temporal == (scenario["category"] == "temporal"), scenario["id"]
        assert directional == (scenario["category"] == "role"), scenario["id"]
