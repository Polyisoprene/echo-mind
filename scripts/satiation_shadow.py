"""Stage 31 S31-3: offline shadow evaluation of social satiation on real history.

Reads a database read-only, replays every inbound message through the satiation model and
reports how many turns would have been suppressed — without touching the running service.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from echomind.mind.bot_belief import rebuild
from echomind.mind.social_satiation import SatiationState


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--chat-key", required=True)
    ap.add_argument("--since-ms", type=int, default=0)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    facts = tuple(con.execute("select subject, fact_text, confidence from semantic_facts"))
    beliefs = rebuild(facts)
    msgs = con.execute(
        "select ts, sender_id, is_self from chat_messages "
        "where chat_key = ? and ts >= ? order by ts",
        (args.chat_key, args.since_ms),
    ).fetchall()
    names = dict(con.execute("select user_id, user_name from social_bonds where chat_key = ?",
                             (args.chat_key,)))
    turns = con.execute(
        "select ts, trigger from turn_traces where chat_key = ? and ts >= ? order by ts",
        (args.chat_key, args.since_ms),
    ).fetchall()
    bot_turns = [
        ts for ts, trigger in turns
        if any(names.get(uid) and str(trigger).startswith(names[uid])
               for uid, belief in beliefs.items() if belief > 0)
    ]

    bot_uid = next(uid for uid, belief in beliefs.items() if belief > 0)
    state = SatiationState()
    ps: list[float] = []
    for ts in bot_turns:
        ps.append(state.willingness(args.chat_key, bot_uid, ts, beliefs[bot_uid]))
        state.record_reply(args.chat_key, bot_uid, ts)
    expected = sum(ps)
    out = {
        "chat_key": args.chat_key,
        "beliefs": beliefs,
        "bot_sender": bot_uid,
        "bot_turns_observed": len(bot_turns),
        "expected_replies_if_probabilistic": round(expected, 1),
        "deterministic_suppression": sum(1 for p in ps if p < 0.5),
        "first_ten_p": [round(p, 2) for p in ps[:10]],
    }
    Path(args.out).mkdir(parents=True, exist_ok=True)
    path = Path(args.out) / "S31_SHADOW_REPORT.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
