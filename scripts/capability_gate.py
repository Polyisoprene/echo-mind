"""Gate: every claimed capability must carry a status and (when implemented) a test.

Also regenerates `docs/CAPABILITY_STATUS.md` so completion claims are a product of
this script rather than something a human edits by hand.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPS = ROOT / "docs" / "capabilities.json"
STATUS_MD = ROOT / "docs" / "CAPABILITY_STATUS.md"
VALID_STATUS = ("implemented", "partial", "absent", "contradicted")
BADGE = {
    "implemented": "✅",
    "partial": "⚠️",
    "absent": "❌",
    "contradicted": "⛔",
}


def _load() -> list[dict[str, Any]]:
    if not CAPS.is_file():
        return []
    data: Any = json.loads(CAPS.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else None
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _resolve(node: str) -> str:
    """Return '' when the pytest node exists, otherwise the reason it does not."""
    if "::" not in node:
        return f"{node!r} is not a pytest node id"
    rel, func = node.split("::", 1)
    path = ROOT / rel
    if not path.is_file():
        return f"missing file {rel}"
    if f"def {func}" not in path.read_text(encoding="utf-8"):
        return f"missing function {func} in {rel}"
    return ""


def _check_status(entry: dict[str, Any], cap: str) -> list[str]:
    status = str(entry.get("status", ""))
    if status not in VALID_STATUS:
        return [f"{cap}: illegal status {status!r}"]
    if status != "implemented" and not str(entry.get("gap", "")).strip():
        return [f"{cap}: status {status} requires a non-empty gap"]
    return []


def _check_test(entry: dict[str, Any], cap: str) -> list[str]:
    node = entry.get("acceptance_test")
    if entry.get("status") == "implemented" and not node:
        return [f"{cap}: implemented without acceptance_test"]
    if not node:
        return []
    reason = _resolve(str(node))
    return [f"{cap}: {reason}"] if reason else []


def _check(entries: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        cap = str(entry.get("id", "<no-id>"))
        if cap in seen:
            problems.append(f"{cap}: duplicate id")
        seen.add(cap)
        problems.extend(_check_status(entry, cap))
        problems.extend(_check_test(entry, cap))
    return problems


def _cell(value: Any) -> str:
    """Escape a value so it cannot break the markdown table."""
    return str(value).replace("|", "\\|")


def _render(entries: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = dict.fromkeys(VALID_STATUS, 0)
    for entry in entries:
        status = str(entry.get("status"))
        counts[status] = counts.get(status, 0) + 1
    lines = [
        "# 能力状态（自动生成，勿手改）",
        "",
        "> 由 `scripts/capability_gate.py` 生成。修改请编辑 `docs/capabilities.json`。",
        "",
        "| 状态 | 数量 |",
        "|---|---|",
        *(f"| {BADGE[k]} {k} | {v} |" for k, v in counts.items()),
        "",
        "| ID | 能力 | 状态 | 缺口 / 验收 |",
        "|---|---|---|---|",
    ]
    for entry in entries:
        status = str(entry.get("status"))
        detail = entry.get("acceptance_test") if status == "implemented" else entry.get("gap", "")
        lines.append(
            f"| {_cell(entry.get('id'))} | {_cell(entry.get('claim'))} "
            f"| {BADGE.get(status, '?')} {status} | {_cell(detail)} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of only rendering")
    args = parser.parse_args()

    entries = _load()
    if not entries:
        print("FAIL: docs/capabilities.json missing or empty")
        return 1

    problems = _check(entries)
    rendered = _render(entries)
    if args.check:
        current = STATUS_MD.read_text(encoding="utf-8") if STATUS_MD.is_file() else ""
        if current != rendered:
            problems.append("docs/CAPABILITY_STATUS.md is stale; run without --check")
    else:
        STATUS_MD.write_text(rendered, encoding="utf-8")
    print(f"capabilities={len(entries)} -> {STATUS_MD.relative_to(ROOT)}")
    if problems:
        for line in problems:
            print(f"FAIL: {line}")
        return 1
    print("OK: capability ledger consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
