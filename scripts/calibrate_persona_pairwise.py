#!/usr/bin/env python
"""Summarize human pairwise choices into model win rates."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval" / "calibration" / "persona_pairwise_v1"
DIMS = {
    "哪条更像真人(A/B/平局/都差)": "more_human",
    "哪条更适合发群(A/B/平局/都差)": "more_group",
}
CHOICES = {"A", "B", "平局", "都差"}


def _choice(value: str) -> str:
    cleaned = value.strip().upper().replace("TIE", "平局").replace("BOTH_BAD", "都差")
    return cleaned if cleaned in CHOICES else ""


def _record(choice: str, pair: dict[str, Any],
            stats: dict[str, dict[str, float]]) -> None:
    a_model, b_model = pair["a"]["model"], pair["b"]["model"]
    for model in (a_model, b_model):
        stats[model]["game"] += 1.0
    if choice == "A":
        stats[a_model]["win"] += 1.0
        stats[b_model]["loss"] += 1.0
    elif choice == "B":
        stats[b_model]["win"] += 1.0
        stats[a_model]["loss"] += 1.0
    elif choice == "平局":
        stats[a_model]["tie"] += 1.0
        stats[b_model]["tie"] += 1.0
    else:
        stats[a_model]["both_bad"] += 1.0
        stats[b_model]["both_bad"] += 1.0


def _agrees(choice: str, pair: dict[str, Any]) -> bool | None:
    a_score = int(pair["a"]["human_overall"])
    b_score = int(pair["b"]["human_overall"])
    if a_score == b_score:
        return None
    better = pair["a"]["model"] if a_score > b_score else pair["b"]["model"]
    if choice == "A":
        return pair["a"]["model"] == better
    if choice == "B":
        return pair["b"]["model"] == better
    return False


def _summarize(rows: list[dict[str, str]], key: dict[str, Any], header: str) -> dict[str, Any]:
    stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"win": 0.0, "loss": 0.0, "tie": 0.0, "both_bad": 0.0, "game": 0.0}
    )
    agree = total = 0
    for row in rows:
        choice = _choice(str(row.get(header, "")))
        pair = key.get(str(row.get("编号", "")).strip())
        if not choice or pair is None:
            continue
        _record(choice, pair, stats)
        result = _agrees(choice, pair)
        if result is not None:
            total += 1
            agree += int(result)
    return {
        "models": {
            model: {
                "games": int(v["game"]),
                "wins": int(v["win"]),
                "losses": int(v["loss"]),
                "ties": int(v["tie"]),
                "both_bad": int(v["both_bad"]),
                "decisive_win_rate": round(
                    v["win"] / (v["win"] + v["loss"]), 3
                ) if (v["win"] + v["loss"]) else 0.0,
                "win_rate": round((v["win"] + 0.5 * v["tie"]) / v["game"], 3)
                if v["game"] else 0.0,
            } for model, v in stats.items()
        },
        "agreement_with_absolute": round(agree / total, 3) if total else 0.0,
        "comparable_pairs": total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=BASE / "pairs.csv")
    parser.add_argument("--key", type=Path, default=BASE / "key.json")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "reports" / "persona_pairwise_human.json"
    )
    args = parser.parse_args()

    key = {item["pair_id"]: item for item in json.loads(
        args.key.read_text(encoding="utf-8"))["pairs"]}
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    result = {name: _summarize(rows, key, header) for header, name in DIMS.items()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not any(value["models"] for value in result.values()):
        print("还没有成对评分，先把 pairs.csv 填好")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
