#!/usr/bin/env python
"""Shadow-compare satiation recovery constants on real history (read-only).

Replays every inbound message through the satiation model with bot_like = 1.0 (the
worst case) and measures how often the deterministic draw would have suppressed the
reply. Bot messages drive `record_reply`, attributed to the most recent human speaker
in that chat (reply linkage is not stored) — an approximation, stated in the output.

Use it before changing TAU_S: it answers "how much cross-burst suppression does this
value actually buy?"
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.mind.social_satiation import SatiationState, _uniform  # noqa: E402

TAUS = (247.0, 600.0, 1176.0, 1800.0)


def simulate(rows: list[tuple[str, int, str, int]], tau: float) -> dict[str, object]:
    state = SatiationState(tau_s=tau)
    last_human: dict[str, str] = {}
    total = suppressed = 0
    per_chat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for chat, ts, sender, is_self in rows:
        if is_self:
            who = last_human.get(chat)
            if who:
                state.record_reply(chat, who, ts)
            continue
        last_human[chat] = sender
        p = state.willingness(chat, sender, ts, 1.0)
        draw = _uniform(f"{chat}:{sender}:{ts}")
        total += 1
        per_chat[chat][0] += 1
        if draw >= p:
            suppressed += 1
            per_chat[chat][1] += 1
    return {
        "tau_s": tau,
        "inbound": total,
        "suppressed": suppressed,
        "suppression_rate": round(suppressed / total, 4) if total else 0.0,
        "per_chat": {
            chat: {"inbound": n, "suppressed": s, "rate": round(s / n, 4)}
            for chat, (n, s) in per_chat.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = [
        (str(chat), int(ts), str(sender), int(is_self))
        for chat, ts, sender, is_self in conn.execute(
            "SELECT chat_key, ts, sender_id, is_self FROM chat_messages ORDER BY chat_key, ts"
        )
    ]
    report = {
        "db": str(args.db),
        "messages": len(rows),
        "assumptions": [
            "bot_like = 1.0 for every sender (worst case)",
            "bot replies attributed to the latest human speaker in the chat",
            "no tier gate: every inbound message is treated as wake-worthy",
        ],
        "results": [simulate(rows, tau) for tau in TAUS],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "satiation_tau_comparison.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in report["results"]:
        print(f"tau={row['tau_s']:>6.0f}s  suppressed={row['suppressed']:>4d}/{row['inbound']}  "
              f"rate={row['suppression_rate']:.2%}")
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
