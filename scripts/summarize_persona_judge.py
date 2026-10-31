#!/usr/bin/env python
"""Summarize persona-judge reports into a comparison matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("persona_consistency", "naturalness", "boundary", "overall")


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glob", default="reports/pj_*.json")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "eval" / "baselines" / "persona-judge-matrix-2026-10.json")
    args = parser.parse_args()

    entries = []
    for path in sorted(ROOT.glob(args.glob)):
        data = _load(path)
        rows = data.get("rows", [])
        summary = data.get("summary", {})
        if len(rows) < 10 or float(summary.get("overall", 0.0)) <= 0:
            continue
        entries.append({
            "generator": data.get("model", "?"),
            "judge": data.get("judge_model", "?"),
            "n": len(rows),
            **{key: summary.get(key, 0.0) for key in KEYS},
            "file": path.name,
        })
    entries.sort(key=lambda item: (-float(item["overall"]), item["generator"]))
    print("| generator | judge | n | consistency | naturalness | boundary | overall |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for item in entries:
        print(f"| {item['generator']} | {item['judge']} | {item['n']} | "
              f"{item['persona_consistency']} | {item['naturalness']} | "
              f"{item['boundary']} | {item['overall']} |")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
