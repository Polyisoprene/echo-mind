#!/usr/bin/env python
"""Envelope of the fast persona state: how big does the offset actually get?

Uses the real inter-message gaps and the configured step/cap/half-life. Two regimes:
  - mixed signals: deltas drawn uniformly from {-4,-2,0,2,4} (zero mean)
  - consistent signal: +2 every turn (a warm stretch)
The point is not to predict, but to show whether STATE_MAX_ABS is reachable in normal
conversation and how fast a mood fades. Read-only.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_GAP_S = 6 * 3600.0
STEPS = 20_000
SEED = 0


def load_gaps(db: Path) -> list[float]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
    for chat, sender, ts in conn.execute(
        "SELECT chat_key, sender_id, ts FROM chat_messages WHERE is_self = 0"
    ):
        by_key[(str(chat), str(sender))].append(int(ts))
    gaps: list[float] = []
    for timestamps in by_key.values():
        timestamps.sort()
        gaps.extend(
            (b - a) / 1000.0
            for a, b in zip(timestamps[:-1], timestamps[1:], strict=True)
            if 0 < (b - a) / 1000.0 <= MAX_GAP_S
        )
    return gaps


def decay(offset: float, gap_s: float, half_life_min: float = 45.0) -> float:
    return offset * 0.5 ** (gap_s / (half_life_min * 60.0))


def run(gaps: list[float], deltas: list[float], rng: random.Random) -> dict[str, float]:
    state = 0.0
    sizes: list[float] = []
    for _ in range(STEPS):
        state = decay(state, rng.choice(gaps))
        state = max(-10.0, min(10.0, state + rng.choice(deltas)))
        sizes.append(abs(state))
    sizes.sort()
    return {
        "mean_abs": round(statistics.fmean(sizes), 2),
        "p50_abs": round(sizes[len(sizes) // 2], 2),
        "p95_abs": round(sizes[int(0.95 * len(sizes))], 2),
        "share_at_least_8": round(sum(1 for s in sizes if s >= 8) / len(sizes), 3),
        "share_at_cap": round(sum(1 for s in sizes if s >= 9.99) / len(sizes), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    gaps = load_gaps(args.db)
    gaps.sort()
    rng = random.Random(SEED)  # noqa: S311 - simulation, not crypto
    mixed = run(gaps, [-4.0, -2.0, 0.0, 2.0, 4.0], rng)
    warm = run(gaps, [2.0], rng)
    report = {
        "gaps": len(gaps),
        "gap_p50_s": round(gaps[len(gaps) // 2], 1),
        "gap_p95_s": round(gaps[int(0.95 * len(gaps))], 1),
        "gap_p99_s": round(gaps[int(0.99 * len(gaps))], 1),
        "decay_per_gap": {
            "p50": round(2 ** (-(gaps[len(gaps) // 2]) / 2700.0), 4),
            "p95": round(2 ** (-(gaps[int(0.95 * len(gaps))]) / 2700.0), 4),
            "p99": round(2 ** (-(gaps[int(0.99 * len(gaps))]) / 2700.0), 4),
        },
        "decay_after_min": {m: round(0.5 ** (m / 45.0), 4) for m in (45, 90, 180)},
        "turns_to_cap": {int(step): int(-(-10 // step)) for step in (1, 2, 4)},
        "mixed_signals": mixed,
        "consistent_warm": warm,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "persona_state_envelope.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
