#!/usr/bin/env python
"""Fit the satiation recovery constant TAU_S from burst structure.

Operationalisation: after a burst of messages from the same person ends, the time
until their next burst is the characteristic time over which reply fatigue has
decayed. With h(t) = h0 * exp(-dt/tau), taking tau = median inter-burst gap means
fatigue is down to 1/e by the time they usually come back.

This is a proxy, not a direct measurement of fatigue: it assumes the return time is
driven by recovery rather than by the person's own schedule. Read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "echomind.db"
BURST_GAP_S = 60.0
MAX_GAP_S = 6 * 3600.0
BOOTSTRAP = 2000
SEED = 0


def inter_burst_gaps(rows: list[tuple[str, str, int]]) -> list[float]:
    by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
    for chat, sender, ts in rows:
        by_key[(chat, sender)].append(ts)
    gaps: list[float] = []
    for timestamps in by_key.values():
        timestamps.sort()
        for previous, current in zip(timestamps[:-1], timestamps[1:], strict=True):
            gap = (current - previous) / 1000.0
            if BURST_GAP_S < gap <= MAX_GAP_S:
                gaps.append(gap)
    return gaps


def median_ci(gaps: list[float]) -> list[float]:
    rng = random.Random(SEED)  # noqa: S311 - bootstrap, not crypto
    medians = []
    for _ in range(BOOTSTRAP):
        draw = [gaps[rng.randrange(len(gaps))] for _ in range(len(gaps))]
        medians.append(statistics.median(draw))
    medians.sort()
    return [
        round(medians[int(0.025 * BOOTSTRAP)], 1),
        round(medians[int(0.975 * BOOTSTRAP)], 1),
    ]


def fit(db: Path) -> dict[str, object]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = [
        (str(c), str(s), int(t))
        for c, s, t in conn.execute(
            "SELECT chat_key, sender_id, ts FROM chat_messages WHERE is_self = 0"
        )
    ]
    gaps = inter_burst_gaps(rows)
    if not gaps:
        raise SystemExit("no inter-burst gaps found")
    gaps.sort()
    fingerprint = hashlib.sha256(
        json.dumps([round(g, 1) for g in gaps], separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "dataset_sha256": fingerprint,
        "messages": len(rows),
        "inter_burst_gaps": len(gaps),
        "median_s": round(statistics.median(gaps), 1),
        "mean_s": round(statistics.fmean(gaps), 1),
        "p25_s": round(gaps[int(0.25 * len(gaps))], 1),
        "p75_s": round(gaps[int(0.75 * len(gaps))], 1),
        "p90_s": round(gaps[int(0.90 * len(gaps))], 1),
        "median_ci95": median_ci(gaps),
        "burst_gap_s": BURST_GAP_S,
        "max_gap_s": MAX_GAP_S,
        "current_tau_s": 1800.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(fit(args.db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
