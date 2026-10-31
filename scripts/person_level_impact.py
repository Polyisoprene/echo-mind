#!/usr/bin/env python
"""P0 impact model: what changes if the relationship becomes person-level?

Compares the current per-venue stance (stored rank-blended depth, per-venue trust,
per-venue affinity) with a person-level mapping:

  trust_person  = message-weighted mean of the venue trust scores
  depth_person  = depth_from_stats over aggregated counters, then a global
                  percentile across all persons (keeps the spread that raw
                  absolute depth loses to the sigmoid)
  warmth        = tanh(depth_person/100 * 1.6)
  patience      = tanh((trust_person - 0.5) * 2)
  play          = tanh((venue_affinity - 50) / 50)   # stays venue-level

Read-only. Prints distributions, top movers and the owner's cross-venue case.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.domain.bond_stats import BondDepthStats  # noqa: E402
from echomind.mind.bond_adapt import percentile_rank  # noqa: E402
from echomind.mind.bond_depth import care_weight  # noqa: E402
from echomind.mind.bond_features import depth_from_stats  # noqa: E402

STANCE_MAX = 8.0
OWNER = "3064615013"


def _sig(depth: float) -> float:
    return math.tanh(depth / 100.0 * 1.6)


def _pat(trust: float) -> float:
    return math.tanh((trust - 0.5) * 2.0)


def _play(aff: float) -> float:
    return math.tanh((aff - 50.0) / 50.0)


def load(db: Path) -> tuple[list[dict], dict[str, dict]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        """SELECT b.chat_key, b.user_id, b.affinity_score, b.trust_score, b.bond_depth,
                  b.msg_count, s.msgs, s.sessions, s.responded_to_her, s.her_msgs,
                  s.replies_to_them, s.impact_sum, s.impact_n, s.betrayals
           FROM social_bonds b
           LEFT JOIN bond_depth_stats s
             ON s.chat_key = b.chat_key AND s.user_id = b.user_id"""
    ).fetchall()
    bonds: list[dict] = []
    per_person: dict[str, dict] = defaultdict(
        lambda: {"msgs": 0, "sessions": 0, "responded_to_her": 0, "her_msgs": 0,
                 "replies_to_them": 0, "impact_sum": 0.0, "impact_n": 0, "betrayals": 0,
                 "weighted_trust": 0.0, "weight": 0, "venues": []}
    )
    for r in rows:
        chat, uid, aff, trust, stored, msg_count = r[:6]
        stats = r[6:]
        has_stats = stats[0] is not None
        bonds.append({"chat": chat, "uid": uid, "aff": aff, "trust": trust,
                      "stored": stored, "msg_count": msg_count or 0,
                      "abs": depth_from_stats(_stats(chat, uid, stats)) if has_stats else None})
        p = per_person[uid]
        p["weighted_trust"] += trust * max(1, msg_count or 0)
        p["weight"] += max(1, msg_count or 0)
        p["venues"].append(chat)
        if has_stats:
            for key, value in zip(
                ("msgs", "sessions", "responded_to_her", "her_msgs",
                 "replies_to_them", "impact_sum", "impact_n", "betrayals"),
                stats, strict=True,
            ):
                p[key] += value
    return bonds, per_person


def _stats(chat: str, uid: str, s: tuple) -> BondDepthStats:
    return BondDepthStats(chat_key=chat, user_id=uid, msgs=int(s[0]), sessions=int(s[1]),
                          responded_to_her=int(s[2]), her_msgs=int(s[3]),
                          replies_to_them=int(s[4]), impact_sum=float(s[5] or 0),
                          impact_n=int(s[6] or 0), betrayals=int(s[7] or 0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    bonds, people = load(args.db)
    # person-level depth from aggregated counters
    depths: dict[str, float] = {}
    for uid, p in people.items():
        if p["msgs"]:
            depths[uid] = depth_from_stats(
                BondDepthStats(chat_key="person", user_id=uid, msgs=p["msgs"],
                               sessions=p["sessions"], responded_to_her=p["responded_to_her"],
                               her_msgs=p["her_msgs"], replies_to_them=p["replies_to_them"],
                               impact_sum=p["impact_sum"], impact_n=p["impact_n"],
                               betrayals=p["betrayals"])
            )
    uids = tuple(depths)
    pctl = dict(zip(uids, percentile_rank(tuple(depths[u] for u in uids)), strict=True))
    for uid, p in people.items():
        p["trust_person"] = round(p["weighted_trust"] / max(1, p["weight"]), 4)
        p["depth_raw"] = round(depths.get(uid, 0.0), 2)
        p["depth_person"] = round(pctl.get(uid, 0.0) * 100.0, 2)

    deltas: list[dict] = []
    for b in bonds:
        p = people[b["uid"]]
        cur = {"warmth": _sig(b["stored"]), "patience": _pat(b["trust"]), "play": _play(b["aff"])}
        new = {"warmth": _sig(p["depth_person"]), "patience": _pat(p["trust_person"]),
               "play": _play(b["aff"])}
        b.update({"cur": cur, "new": new,
                  "d_warmth": round((new["warmth"] - cur["warmth"]) * STANCE_MAX, 2),
                  "d_patience": round((new["patience"] - cur["patience"]) * STANCE_MAX, 2)})
        b["care_cur"] = care_weight(b["aff"], b["trust"], b["stored"])
        b["care_new"] = care_weight(b["aff"], p["trust_person"], p["depth_person"])
        deltas.append(b)

    def summary(key: str) -> dict:
        xs = [b[key] for b in deltas]
        return {"min": round(min(xs), 2), "mean": round(statistics.mean(xs), 2),
                "max": round(max(xs), 2),
                "gt2": sum(1 for x in xs if abs(x) > 2),
                "gt4": sum(1 for x in xs if abs(x) > 4),
                "n": len(xs)}

    movers = sorted(deltas, key=lambda b: abs(b["d_warmth"]), reverse=True)[:8]
    owner_rows = [b for b in deltas if b["uid"] == OWNER]
    msgs = [p["msgs"] for p in people.values() if p["msgs"]]
    report = {
        "bonds": len(bonds),
        "people_with_stats": len(uids),
        "trust_aggregation": {uid: round(p["trust_person"], 3) for uid, p in people.items()
                              if len(p["venues"]) > 1},
        "warmth_delta": summary("d_warmth"),
        "patience_delta": summary("d_patience"),
        "top_movers": [
            {"uid": b["uid"], "chat": b["chat"], "stored": b["stored"],
             "abs": None if b["abs"] is None else round(b["abs"], 1),
             "depth_person": people[b["uid"]]["depth_person"],
             "d_warmth": b["d_warmth"], "d_patience": b["d_patience"]}
            for b in movers
        ],
        "owner": [
            {"chat": b["chat"], "stored": b["stored"],
             "depth_person": people[b["uid"]]["depth_person"],
             "trust": b["trust"], "trust_person": people[b["uid"]]["trust_person"],
             "d_warmth": b["d_warmth"], "d_patience": b["d_patience"],
             "care_cur": b["care_cur"], "care_new": b["care_new"]}
            for b in owner_rows
        ],
        "care_delta": {
            "mean": round(statistics.mean(b["care_new"] - b["care_cur"] for b in deltas), 4),
            "max_up": round(max(b["care_new"] - b["care_cur"] for b in deltas), 4),
            "max_down": round(min(b["care_new"] - b["care_cur"] for b in deltas), 4),
        },
        "person_msgs_p50_p95": [round(statistics.median(msgs), 1),
                                round(sorted(msgs)[int(0.95 * (len(msgs) - 1))], 1)],
        "current_saturation": 452.0,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "person_level_impact.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
