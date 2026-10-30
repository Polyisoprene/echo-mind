"""Compare the current gate (M1) with a homeostatic model (M2) on real messages.

Uses the live probe for role/topic_pull, so it costs a few dozen LLM calls.
"""

from __future__ import annotations

import asyncio
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.core.config import load_config_from_json
from echomind.domain.models import Percept
from echomind.mind.drives import compute_care_weight
from echomind.mind.salience_hydraulics import (
    _positive_factors,
    _negative_factors,
    check_implicit_second_person_ask,
    check_self_utterance_resonance,
    tokenize_query,
)
from echomind.mind.subconscious_probe import SubconsciousChordProbe

DB = Path("/home/polyisoprene/Documents/echo-mind/data/echomind.db")
CHAT = "group:10002002"
T0, T1 = 1793250000000, 1793289000000     # 13:00 -> 21:30 local
LIMIT = 80          # 每个分层取 80 条（有回合 / 无回合）


CACHE = Path("/tmp/wake_probe_cache.json")


async def _probe_all(percepts: list[Percept], ctx: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    cfg = load_config_from_json(Path("/home/polyisoprene/Documents/echo-mind/data/config.json"))
    db = SqliteDatabase(Path("/tmp/compare.db")); await db.initialize()
    llm = FailoverLlmGateway(cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain)
    probe = SubconsciousChordProbe(llm)
    sem = asyncio.Semaphore(4)
    out: dict[str, Any] = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    async def one(p: Percept) -> None:
        async with sem:
            chord = await probe.appraise(p, ctx.get(p.message_id, ()), None, timeout_s=12.0)
            out[p.message_id] = None if chord is None else {
                "role": chord.role, "topic_pull": chord.topic_pull
            }

    await asyncio.gather(*(one(p) for p in percepts if p.message_id not in out))
    CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


async def main() -> None:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "select ts, sender_id, sender_name, is_self, text, mid from chat_messages "
        "where chat_key=? and ts between ? and ? order by ts", (CHAT, T0, T1)).fetchall()
    turns = {ts for ts, _ in con.execute(
        "select ts, trigger from turn_traces where chat_key=? and ts between ? and ?", (CHAT, T0, T1))}

    db = SqliteDatabase(DB); await db.initialize()
    work = SqliteWorkingStateStore(db); mem = SqliteMemoryRepository(db)
    snap = await work.load_working_state("global"); params = await work.get_plastic_params()
    talk = params["talkativeness"].value
    th_m1 = round(max(0.48, min(0.76, 0.86 - (talk * (0.5 + 0.5 * snap.affect.energy / 100)) / 210)), 2)

    history: list[tuple[int, str, str, bool, str]] = []
    positives: list[tuple[Percept, str, bool]] = []
    negatives: list[tuple[Percept, str, bool]] = []
    samples: list[tuple[Percept, str, bool]] = []
    last_speak = T0
    bonds: dict[str, Any] = {}
    for ts, uid, name, is_self, text, mid in rows:
        line = f"{'我' if is_self else name}: {(text or '')[:60]}"
        if is_self:
            last_speak = ts
            history.append((ts, uid, text or "", True, mid))
            continue
        ctx = tuple(f"{'我' if h[3] else '群友'}: {h[2][:50]}" for h in history[-6:])
        named = any(k in (text or "") for k in ("回音", "尾尾", "@"))
        if not named:
            p = Percept(chat_key=CHAT, scene="group", message_id=mid, timestamp_ms=ts,
                        sender_id=uid, sender_name=name, text=text or "")
            actual = any(ts <= t <= ts + 8000 for t in turns)
            bucket = positives if actual else negatives
            if len(bucket) < LIMIT:
                bucket.append((p, ctx, actual))
            if uid not in bonds:
                b = await mem.get_social_bond(CHAT, uid)
                if b: bonds[uid] = b
        history.append((ts, uid, text or "", False, mid))

    samples = positives + negatives
    chords = await _probe_all([s[0] for s in samples], {s[0].message_id: s[1] for s in samples})

    m1 = m2 = 0
    m1_hit = m2_hit = 0
    maxts = {p.message_id: p.timestamp_ms for p, _, _ in samples}
    for p, _ctx, actual in samples:
        ch = chords.get(p.message_id) or {}
        care = compute_care_weight(p.sender_id, bonds.get(p.sender_id))
        # ---- M1 current gate (non-summon paths) ----
        pos, _pt = _positive_factors(p, snap, (), False, known_vocab=frozenset(),
                                     params=params, speaker_bond=bonds.get(p.sender_id))
        neg, _nt = _negative_factors(p, snap, (), False, params, speaker_bond=bonds.get(p.sender_id))
        drv = max(0.0, round((snap.drives.social_expression - 42.0) / 300.0, 2))
        ambient = round(max(0.10, min(0.84, 0.35 + pos + drv - neg)), 2)
        chime = round((0.28 + 0.72 * care) * (snap.drives.social_expression / 100.0)
                      * (ch.get("topic_pull", 0) / 3.0), 2)
        ask = check_implicit_second_person_ask(p, 0, 0)
        w1 = ambient >= th_m1 or chime >= 0.34 or bool(ask) or ch.get("role") == "direct_to_me"
        # ---- M2 homeostatic ----
        gap = max(0, p.timestamp_ms - last_speak)
        urge = min(1.0, 1.0 - math.exp(-gap / 600000.0))
        theta = max(0.20, 0.95 - 0.60 * urge)
        impulse = 0.5 * (ch.get("topic_pull", 0) / 3.0) + 0.5 * care
        w2 = ch.get("role") == "direct_to_me" or impulse >= theta
        m1 += w1; m2 += w2
        m1_hit += w1 and actual; m2_hit += w2 and actual
        _ = tokenize_query  # documented but unused in this approximation

    total = len(samples)
    actual_n = sum(1 for _, _, a in samples if a)
    print(json.dumps({
        "sample": total, "positives": len(positives), "negatives": len(negatives),
        "M1_wakes": m1, "M2_wakes": m2,
        "M1_hits": m1_hit, "M2_hits": m2_hit,
        "M1_rate": round(m1 / max(1, total), 2), "M2_rate": round(m2 / max(1, total), 2),
        "M1_recall": round(m1_hit / max(1, actual_n), 2), "M2_recall": round(m2_hit / max(1, actual_n), 2),
        "threshold_M1": th_m1,
        "by_role": _by_role(samples, chords),
    }, ensure_ascii=False, indent=2))


def _by_role(samples: list[tuple[Percept, str, bool]], chords: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, dict[str, int]] = {}
    for p, _c, actual in samples:
        role = (chords.get(p.message_id) or {}).get("role", "none")
        rec = out.setdefault(role, {"n": 0, "actual": 0})
        rec["n"] += 1
        rec["actual"] += 1 if actual else 0
    return out


if __name__ == "__main__":
    asyncio.run(main())
