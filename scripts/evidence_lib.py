"""Shared helpers for the evidence ledgers (parameter provenance & capability claims).

This module is the single implementation of "what counts as a tunable constant".
Both `param_audit.py` (writer) and `param_gate.py` (checker) import it so the
scanner can never disagree with the gate.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "echomind"
PACKAGES = ("mind", "domain")
LEDGER_PATH = ROOT / "docs" / "params" / "ledger.json"
BASELINE_PATH = ROOT / "docs" / "params" / "baseline.json"

TAG_RE = re.compile(r"param:\s*(src|convention|fit)\b", re.IGNORECASE)
ALLOWED_CLASSES = ("src", "data", "convention", "fit_pending", "unknown")
CLASS_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "src": ("evidence.doi", "evidence.locator", "evidence.derivation"),
    "data": (
        "evidence.dataset_sha256",
        "evidence.n",
        "evidence.estimate",
        "evidence.ci95",
        "evidence.script",
    ),
    "convention": ("evidence.rationale",),
    "fit_pending": ("issue", "experiment", "conservative_value"),
    "unknown": (),
}


def _numeric(node: ast.AST) -> bool:
    """True when a literal node carries numbers (so the constant is tunable)."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, (ast.Tuple, ast.List)):
        return bool(node.elts) and all(_numeric(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        keys = [k for k in node.keys if k is not None]
        return bool(node.values) and all(_numeric(v) for v in node.values) and len(keys) == len(
            node.values
        )
    return False


def _literal_text(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        body = ", ".join(_literal_text(item) for item in node.elts)
        return f"[{body}]" if isinstance(node, ast.List) else f"({body})"
    if isinstance(node, ast.Dict):
        pairs = (
            f"{_literal_text(key)}: {_literal_text(value)}"
            for key, value in zip(node.keys, node.values, strict=True)
            if key is not None
        )
        return "{" + ", ".join(pairs) + "}"
    return ""


def _value_text(node: ast.AST, lines: list[str]) -> str:
    literal = _literal_text(node)
    if literal:
        return literal[:200]
    span = "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])
    return " ".join(span.split())[:200]


def _tag_before(lines: list[str], lineno: int) -> str:
    """Return the `param:` tag declared within the 3 lines above a constant."""
    head = " ".join(lines[max(0, lineno - 4) : lineno])
    match = TAG_RE.search(head)
    return match.group(1).lower() if match else ""


def _classify(tag: str) -> tuple[str, dict[str, Any]]:
    """Map an in-code tag onto a ledger class plus the evidence we can extract."""
    if tag == "src":
        return "src", {"raw_tag": "src"}
    if tag == "convention":
        return "convention", {"raw_tag": "convention"}
    if tag == "fit":
        return "fit_pending", {"raw_tag": "fit:pending"}
    return "unknown", {}


def _tunable(node: ast.AST) -> tuple[str, ast.AST] | None:
    """Return (name, value_node) when the statement declares a tunable constant."""
    if isinstance(node, ast.Assign):
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        target, value = node.target, node.value
    else:
        return None
    if not isinstance(target, ast.Name):
        return None
    name = target.id
    if not name.isupper() or name.startswith("_"):
        return None
    if not _numeric(value):
        return None
    return name, value


def _module_entries(path: Path) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    rel = path.relative_to(SRC).as_posix()
    entries: list[dict[str, Any]] = []
    for node in tree.body:
        found = _tunable(node)
        if found is None:
            continue
        name, value = found
        klass, evidence = _classify(_tag_before(lines, node.lineno))
        entries.append(
            {
                "id": f"{rel}::{name}",
                "module": rel,
                "symbol": name,
                "line": node.lineno,
                "value": _value_text(value, lines),
                "class": klass,
                "status": "quarantined" if klass == "unknown" else "active",
                "claim": "",
                "evidence": evidence,
            }
        )
    return entries


def scan() -> list[dict[str, Any]]:
    """Collect every tunable module-level constant under mind/ and domain/."""
    entries = [
        entry
        for package in PACKAGES
        for path in sorted((SRC / package).rglob("*.py"))
        for entry in _module_entries(path)
    ]
    entries.sort(key=lambda item: (item["module"], int(item["line"])))
    return entries


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_ledger() -> dict[str, dict[str, Any]]:
    """Ledger entries keyed by id (module::SYMBOL)."""
    data = load_json(LEDGER_PATH)
    raw = data.get("entries")
    if not isinstance(raw, list):
        return {}
    return {
        str(entry["id"]): entry
        for entry in raw
        if isinstance(entry, dict) and "id" in entry
    }


def merge(
    existing: dict[str, dict[str, Any]], scanned: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Keep human annotations, refresh location/value, add newly found constants."""
    merged: dict[str, dict[str, Any]] = {}
    for entry in scanned:
        key = str(entry["id"])
        previous = existing.get(key, {})
        combined = {**entry, **{k: v for k, v in previous.items() if k not in ("line", "value")}}
        combined["line"] = entry["line"]
        combined["value"] = entry["value"]
        merged[key] = combined
    return merged


def required_for(klass: str) -> tuple[str, ...]:
    return CLASS_REQUIREMENTS.get(klass, ())


def get_field(entry: dict[str, Any], dotted: str) -> Any:
    """Read a dotted path such as `evidence.doi` from a ledger entry."""
    current: Any = entry
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def is_compliant(entry: dict[str, Any]) -> bool:
    """A compliant entry declares a known class and carries all required evidence."""
    klass = str(entry.get("class", "unknown"))
    if klass not in ALLOWED_CLASSES or klass == "unknown":
        return False
    required = required_for(klass)
    return all(get_field(entry, field) not in (None, "", []) for field in required)
