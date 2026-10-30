"""PARAM-01/02: every tunable constant must declare where its value comes from."""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "echomind"
TAGGED_FILES = (
    "mind/bond_depth.py",
)
TAG = "param:"
KINDS = ("src:", "convention:", "fit:")


def _module_constants(tree: ast.Module) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        if names and names[0].isupper():
            out.append((names[0], node.lineno, node.end_lineno or node.lineno))
    return out


def test_every_tunable_constant_declares_provenance() -> None:
    """Each UPPER_CASE module constant must carry a `param:` provenance tag."""
    missing: list[str] = []
    for rel in TAGGED_FILES:
        path = SRC_ROOT / rel
        lines = path.read_text(encoding="utf-8").splitlines()
        tree = ast.parse("\n".join(lines))
        for name, start, end in _module_constants(tree):
            span = " ".join(lines[start - 1:end])
            if TAG not in span or not any(k in span for k in KINDS):
                missing.append(f"{rel}:{start} {name}")
    assert not missing, f"constants without `param: src:|convention:|fit:` provenance: {missing}"
