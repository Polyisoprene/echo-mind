"""Stage 30 I-8: the 7D persona defaults have exactly one definition site."""

from __future__ import annotations

import ast
from pathlib import Path

from echomind.adapters.storage.working_repo import DEFAULT_PLASTIC_PARAMS
from echomind.domain.persona_specs import PERSONA_SPECS
from echomind.mind.plasticity import PARAM_BASELINES

SRC = Path(__file__).resolve().parents[2] / "src" / "echomind"


def test_storage_defaults_come_from_the_shared_table() -> None:
    stored = {spec.key: spec for spec in DEFAULT_PLASTIC_PARAMS}
    for key, spec in PERSONA_SPECS.items():
        assert stored[key].value == spec.default
        assert stored[key].min_bound == spec.min_bound
        assert stored[key].max_bound == spec.max_bound


def test_plasticity_baselines_come_from_the_shared_table() -> None:
    for key, spec in PERSONA_SPECS.items():
        assert PARAM_BASELINES[key] == spec.default


def test_consumers_never_pass_literal_defaults() -> None:
    offenders: list[str] = []
    for rel in ("mind/personality.py", "mind/salience_hydraulics.py"):
        tree = ast.parse((SRC / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or len(node.args) < 3:
                continue
            name = getattr(node.func, "id", "")
            if name not in ("_val", "_p_val"):
                continue
            third = node.args[2]
            if isinstance(third, ast.Constant) and isinstance(third.value, (int, float)):
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"literal persona defaults reintroduced at {offenders}"
