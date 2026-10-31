#!/usr/bin/env python
"""E1-A: rank sensitivity of bond depth under +-20% parameter perturbation.

Reads persisted counters (bond_depth_stats), recomputes depth under each perturbed
constant, and reports how much the *ordering* of contacts changes (Spearman) plus the
largest absolute depth shift. A parameter that keeps rank >= 0.95 and shifts depth by
< 1 point is a candidate for `convention`: the exact value does not change decisions.

Read-only. Uses mock patching because the model reads module-level constants.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import echomind.mind.bond_depth as bd  # noqa: E402
import echomind.mind.bond_features as bf  # noqa: E402
from echomind.domain.bond_stats import BondDepthStats  # noqa: E402
from echomind.mind.bond_features import depth_from_stats  # noqa: E402

FACTORS = (0.8, 1.2)
WEIGHTS = ("W_FREQ", "W_DIV", "W_IMPACT", "W_RECIP", "W_RESP", "W_BETRAY", "BIAS", "GAIN")
SATURATIONS = ("FREQ_SATURATION", "DIVERSITY_SATURATION", "IMPACT_SATURATION",
               "BETRAYAL_HALF_LIFE")
RANK_FLOOR = 0.95
DEPTH_FLOOR = 1.0


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _spearman(a: list[float], b: list[float]) -> float:
    ra, rb = _ranks(a), _ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    return 1.0 if va == 0 or vb == 0 else cov / math.sqrt(va * vb)


def _depths(rows: list[BondDepthStats]) -> dict[str, float]:
    return {f"{r.chat_key}|{r.user_id}": depth_from_stats(r) for r in rows}


def _load(db: Path) -> list[BondDepthStats]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    return [
        BondDepthStats(
            chat_key=str(c), user_id=str(u), msgs=int(m), her_msgs=int(h),
            replies_to_them=int(r), responded_to_her=int(o), sessions=int(s),
            impact_sum=float(i), impact_n=int(n), betrayals=int(b), updated_ms=int(t),
        )
        for c, u, m, h, r, o, s, i, n, b, t in conn.execute(
            "SELECT chat_key, user_id, msgs, her_msgs, replies_to_them, responded_to_her, "
            "sessions, impact_sum, impact_n, betrayals, updated_ms FROM bond_depth_stats"
        )
    ]


def _perturb(rows: list[BondDepthStats], name: str, factor: float) -> dict[str, float]:
    base = int(getattr(bd, name)) if name in SATURATIONS else float(getattr(bd, name))
    value = base * factor
    targets = [bd] + ([bf] if name in SATURATIONS else [])
    with mock.patch.multiple(*targets, **{name: value}):
        return _depths(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    rows = _load(args.db)
    baseline = _depths(rows)
    keys_by_chat: dict[str, list[str]] = {}
    for row in rows:
        keys_by_chat.setdefault(row.chat_key, []).append(f"{row.chat_key}|{row.user_id}")
    ranked = {chat: keys for chat, keys in keys_by_chat.items() if len(keys) >= 3}
    results = []
    for name in WEIGHTS + SATURATIONS:
        for factor in FACTORS:
            depths = _perturb(rows, name, factor)
            rhos = [
                _spearman([baseline[k] for k in keys], [depths[k] for k in keys])
                for keys in ranked.values()
            ]
            deltas = [abs(depths[k] - baseline[k]) for k in baseline]
            results.append({
                "param": name, "factor": factor,
                "min_rank": round(min(rhos), 4) if rhos else 1.0,
                "max_depth_delta": round(max(deltas), 3),
                "quiet": bool(rhos) and min(rhos) >= RANK_FLOOR and max(deltas) < DEPTH_FLOOR,
            })
    quiet = sorted({r["param"] for r in results if r["quiet"]})
    report = {
        "rows": len(rows),
        "chats_ranked": {chat: len(keys) for chat, keys in ranked.items()},
        "factors": FACTORS,
        "criteria": {"rank_floor": RANK_FLOOR, "depth_floor": DEPTH_FLOOR},
        "quiet_params": quiet,
        "results": results,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "bond_param_sensitivity.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in results:
        mark = "quiet" if row["quiet"] else "LOUD "
        print(f"{mark} {row['param']:22s} x{row['factor']:.1f} "
              f"rank={row['min_rank']:.3f} dmax={row['max_depth_delta']:.2f}")
    print(f"quiet: {quiet}")
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
