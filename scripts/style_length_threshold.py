#!/usr/bin/env python
"""Report the observed high-score reply length distribution (human labels)."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "eval" / "calibration" / "persona_v1" / "items.csv"


def main() -> int:
    raw = PATH.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    lengths = sorted(len(r["她的回复"]) for r in rows if int(r["总体(1-5)"]) >= 4)
    report = {
        "n": len(lengths),
        "median": statistics.median(lengths),
        "p75": lengths[3 * len(lengths) // 4],
        "max": max(lengths),
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
