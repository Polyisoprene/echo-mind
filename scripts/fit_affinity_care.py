#!/usr/bin/env python
"""Report affinity percentiles and the care-weight impact of a q50 calibration (D11)."""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.storage.database import SqliteDatabase  # noqa: E402
from echomind.adapters.storage.person_level_repo import load_bonds, load_stats  # noqa: E402
from echomind.mind.bond_depth import AFFINITY_OFFSET, AFFINITY_SPAN, care_weight  # noqa: E402
from echomind.mind.person_level import build_profiles  # noqa: E402


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    pos = (len(values) - 1) * q
    low, high = int(pos), min(int(pos) + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (pos - low)


async def main() -> int:
    db = SqliteDatabase(ROOT / "data" / "echomind.db")
    await db.initialize()
    profiles = build_profiles(await load_bonds(db), await load_stats(db))
    affinities = sorted(p.affinity for p in profiles.values())
    q50 = statistics.median(affinities) if affinities else 0.0
    suggested = {"offset": round(q50, 2), "span": round(100.0 - q50, 2)}
    rows = []
    for p in profiles.values():
        base = max(0.0, min(1.0, (p.affinity - q50) / max(1e-9, 100.0 - q50)))
        bonus = 1.0 + 0.35 * max(0.0, min(1.0, p.depth_raw / 100.0))
        rows.append({
            "person_id": p.person_id, "affinity": round(p.affinity, 2),
            "old": care_weight(p.affinity, p.trust, p.depth_raw),
            "new": round(min(0.97, base * max(0.0, min(1.0, p.trust)) * bonus), 3),
        })
    payload = {
        "n": len(profiles),
        "percentiles": {q: round(_percentile(affinities, q), 2)
                        for q in (0.25, 0.5, 0.75, 0.9)},
        "current": {"offset": AFFINITY_OFFSET, "span": AFFINITY_SPAN},
        "suggested": suggested,
        "max_abs_delta": round(max((abs(r["new"] - r["old"]) for r in rows), default=0.0), 3),
        "rows": rows,
    }
    out = ROOT / "reports" / "affinity_care_calibration.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("n", "percentiles", "current", "suggested", "max_abs_delta")},
                     ensure_ascii=False))
    print(f"report: {out}")
    print("apply via ECHOMIND_AFFINITY_OFFSET/SPAN after choosing a target")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
