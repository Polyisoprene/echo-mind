#!/usr/bin/env python
"""Compute quadratic weighted kappa between human labels and judge scores."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval" / "calibration" / "persona_v1"
DIMS = {
    "人格一致性(1-5)": "persona_consistency",
    "自然度(1-5)": "naturalness",
    "边界感(1-5)": "boundary",
    "总体(1-5)": "overall",
}


def _qwk(human: list[int], judge: list[int], k: int = 5) -> float:
    if not human:
        return 0.0
    observed = [[0.0] * k for _ in range(k)]
    for h, j in zip(human, judge, strict=True):
        observed[h - 1][j - 1] += 1
    total = float(len(human))
    observed = [[value / total for value in row] for row in observed]
    hist_h = [sum(observed[i]) for i in range(k)]
    hist_j = [sum(observed[i][j] for i in range(k)) for j in range(k)]
    expected = [[hist_h[i] * hist_j[j] for j in range(k)] for i in range(k)]
    weights = [[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)]
    numerator = sum(weights[i][j] * observed[i][j] for i in range(k) for j in range(k))
    denominator = sum(weights[i][j] * expected[i][j] for i in range(k) for j in range(k))
    return 1.0 - numerator / denominator if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=BASE / "items.csv")
    parser.add_argument("--key", type=Path, default=BASE / "key.json")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "calibration_kappa.json")
    args = parser.parse_args()

    payload = json.loads(args.key.read_text(encoding="utf-8"))
    key = {item["item_id"]: item for item in payload["items"]}
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    result: dict[str, Any] = {"n": 0, "dims": {}}
    for header, judge_key in DIMS.items():
        human: list[int] = []
        judge: list[int] = []
        for row in rows:
            raw = str(row.get(header, "")).strip()
            item = key.get(str(row.get("编号", "")).strip())
            if not raw or item is None:
                continue
            human.append(int(raw))
            score = float(item["judge_scores"].get(judge_key, 0))
            judge.append(max(1, min(5, round(score))))
        if human:
            mae = sum(abs(h - j) for h, j in zip(human, judge, strict=True)) / len(human)
            result["dims"][judge_key] = {"n": len(human),
                                         "qwk": round(_qwk(human, judge), 3),
                                         "mae": round(mae, 3)}
            result["n"] = max(result["n"], len(human))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["dims"]:
        print("还没有人工评分，先把 items.csv 填好")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
