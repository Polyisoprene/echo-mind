#!/usr/bin/env python
"""Fit the affinity level thresholds from observed bonds (quantiles of active bonds).

Dormant bonds sit exactly at the default score (30.0) and would collapse several
quantiles onto one value, so they are excluded from the fit; they stay at Lv.1 by
construction because every threshold is above 30.

Read-only: prints the estimate, bootstrap CI and a dataset fingerprint. Paste the
estimate into `AFFINITY_THRESHOLDS` and the CI into the ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "echomind.db"
DORMANT = 30.0
QUANTILES = (0.25, 0.50, 0.75, 0.90)
BOOTSTRAP = 2000
SEED = 0


def linear_quantile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    pos = p * (len(values) - 1)
    low = int(pos)
    high = min(low + 1, len(values) - 1)
    return values[low] * (1 - (pos - low)) + values[high] * (pos - low)


def fit(values: list[float]) -> dict[str, float]:
    active = sorted(v for v in values if v > DORMANT + 1e-9)
    estimate = [round(linear_quantile(active, p), 2) for p in QUANTILES]
    rng = random.Random(SEED)  # noqa: S311 - bootstrap, not crypto
    samples = {p: [] for p in QUANTILES}
    for _ in range(BOOTSTRAP):
        draw = sorted(rng.choice(active) for _ in active)
        for p in QUANTILES:
            samples[p].append(linear_quantile(draw, p))
    ci = {
        str(p): [
            round(sorted(samples[p])[int(0.025 * BOOTSTRAP)], 2),
            round(sorted(samples[p])[int(0.975 * BOOTSTRAP)], 2),
        ]
        for p in QUANTILES
    }
    fingerprint = hashlib.sha256(
        json.dumps(sorted(values), separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "n_total": len(values),
        "n_active": len(active),
        "estimate": estimate,
        "ci95": ci,
        "dataset_sha256": fingerprint,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    values = [float(r[0]) for r in conn.execute("SELECT affinity_score FROM social_bonds")]
    result = fit(values)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("thresholds ->", tuple(result["estimate"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
