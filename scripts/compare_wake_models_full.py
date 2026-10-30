"""Full-fidelity replay: M1 (current gate) vs M2 (homeostatic) vs A (hybrid).

Uses the real probe, real bond care, real plastic params and a simulated drive tank.
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
    _negative_factors, _positive_factors, check_implicit_second_person_ask,
    check_self_utterance_resonance, tokenize_query,
)
from echomind.mind.subconscious_probe import SubconsciousChordProbe

ROOT = Path(os.getenv("ECHOMIND_ROOT", "."))
DB = ROOT / "data/echomind.db"
CHAT = "group:10002002"
DAY0 = 1793250000000          # 2026-10-30 13:00 local（活跃时段）
END = 1793289000000           # 21:30
CACHE = Path("/tmp/wake_probe_cache_full.json")


async def probe_all(percepts: list[Percept], ctx: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    cfg = load_config_from_json(ROOT / "data/config.json")
    db = SqliteDatabase(Path("/tmp/wake_full.db")); await db.initialize()
    llm = FailoverLlmGateway(cfg.primary_llm, cfg.fallback_llm, db,
                             extra_fallbacks=cfg.fallback_chain)
    probe = SubconsciousChordProbe(llm)
    out: dict[str, Any] = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    sem = asyncio.Semaphore(8)

    async def one(p: Percept) -> None:
        async with sem:
            chord = await probe.appraise(p, ctx.get(p.message_id, ()), None, timeout_s=15.0)
            out[p.message_id] = None if chord is None else {
                "role": chord.role, "topic_pull": chord.topic_pull}

    await asyncio.gather(*(one(p) for p in percepts if p.message_id not in out))
    CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


async def main() -> None:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "select ts,sender_id,sender_name,is_self,text,mid from chat_messages "
        "where chat_key=? and ts between ? and ? order by ts", (CHAT, DAY0, END)).fetchall()
    turn_rows = con.execute(
        "select ts,trigger from turn_traces where chat_key=? and ts between ? and ?",
        (CHAT, DAY0, END)).fetchall()
    turns: list[tuple[int, str, str]] = []
    for t, trig in turn_rows:
        trig = str(trig or "")
        name_part, _, text_part = trig.partition("：")
        turns.append((t, name_part.strip(), text_part.strip()[:24]))

    actual_mids: set[str] = set()
    by_sender: dict[str, list[tuple[int, str, str]]] = {}
    for ts, uid, name, is_self, text, mid in rows:
        if not is_self:
            by_sender.setdefault(name or "", []).append((ts, (text or "").strip()[:15], mid))
    for t, name, seg in turns:
        best = None
        for ts, head, mid in by_sender.get(name, []):
            if ts <= t <= ts + 120000 and head and seg.startswith(head[:8]):
                best = mid
        if best:
            actual_mids.add(best)

    def matched(mid: str) -> bool:
        return mid in actual_mids
    db = SqliteDatabase(DB); await db.initialize()
    work = SqliteWorkingStateStore(db); mem = SqliteMemoryRepository(db)
    snap = await work.load_working_state("global"); params = await work.get_plastic_params()
    bonds: dict[str, Any] = {}
    for uid in {r[1] for r in rows if not r[3]}:
        b = await mem.get_social_bond(CHAT, uid)
        if b: bonds[uid] = b
    talk = params["talkativeness"].value

    history: list[tuple[int, str, bool, str]] = []
    need: list[tuple[Percept, str]] = []
    meta: dict[str, tuple[int, str, bool, str, bool]] = {}
    rival = {u for u, b in bonds.items() if b.is_rival}
    for ts, uid, name, is_self, text, mid in rows:
        text = text or ""
        named = any(k in text for k in ("回音", "尾尾", "@"))
        if not is_self:
            ctx = tuple(f"{'我' if h[2] else '群友'}: {h[3][:50]}" for h in history[-6:])
            if not named:
                p = Percept(chat_key=CHAT, scene="group", message_id=mid,
                            timestamp_ms=ts, sender_id=uid, sender_name=name, text=text)
                need.append((p, ctx))
            meta[mid] = (ts, uid, is_self, text, named)
        history.append((ts, uid, is_self, text))

    chords = await probe_all([p for p, _ in need], dict(need))
    th0 = round(max(0.48, min(0.76, 0.86 - (talk * (0.5 + 0.5 * snap.affect.energy / 100)) / 210)), 2)

    state = {"M1": {"soc": snap.drives.social_expression, "last": DAY0},
             "M2": {"U": 0.0, "last": DAY0},
             "A": {"soc": snap.drives.social_expression, "U": 0.0, "last": DAY0}}
    wakes = {"M1": [], "M2": [], "A": []}
    hit = {"M1": 0, "M2": 0, "A": 0}
    miss = {"M1": 0, "M2": 0, "A": 0}
    fp = {"M1": 0, "M2": 0, "A": 0}
    last_text = ""
    actual_count = 0

    for ts, uid, name, is_self, text, mid in rows:
        actual = matched(mid)
        for m in ("M1", "M2", "A"):
            st = state[m]
            dt_min = max(0.0, (ts - st["last"]) / 60000.0)
            if m in ("M1", "A"):
                st["soc"] = min(100.0, st["soc"] + min(6.0, dt_min * 0.15))
            if m in ("M2", "A"):
                st["U"] = min(1.0, st["U"] + (1 - st["U"]) * min(1.0, (ts - st["last"]) / 600000.0))
        if is_self:
            for m in ("M1", "A"): state[m]["soc"] = max(22.0, state[m]["soc"] - 22.0)
            for m in ("M2", "A"): state[m]["U"] *= 0.2
            for m in ("M1", "M2", "A"): state[m]["last"] = ts
            last_text = text
            continue
        if name and mid in meta and meta[mid][4]:
            continue
        ch = chords.get(mid) or {}
        tp = ch.get("topic_pull", 0); role = ch.get("role", "none")
        care = compute_care_weight(uid, bonds.get(uid))
        p = Percept(chat_key=CHAT, scene="group", message_id=mid, timestamp_ms=ts,
                    sender_id=uid, sender_name=name, text=text)
        pos, _ = _positive_factors(p, snap, (), False, known_vocab=frozenset(),
                                   params=params, speaker_bond=bonds.get(uid))
        neg, _ = _negative_factors(p, snap, (), False, params, speaker_bond=bonds.get(uid))
        for m in ("M1", "M2", "A"):
            soc = state[m].get("soc", snap.drives.social_expression)
            U = state[m].get("U", 0.0)
            drv = max(0.0, round((soc - 42.0) / 300.0, 2))
            score = round(max(0.10, min(0.84, 0.35 + pos + drv - neg)), 2)
            chime = (0.28 + 0.72 * care) * (soc / 100.0) * (tp / 3.0)
            theta = th0
            if m in ("M2", "A"):
                theta = max(0.20, 0.95 - 0.60 * U)
            if m == "M1":
                residue = {"g": (ts, last_text, 0)}
                res_hit, _ = check_self_utterance_resonance(p, residue, tuple(rival))
                wake = role == "direct_to_me" or chime >= 0.34 or res_hit
            elif m == "M2":
                impulse = 0.5 * (tp / 3.0) + 0.5 * care
                wake = role == "direct_to_me" or impulse >= theta
            else:
                wake = role == "direct_to_me" or score >= max(0.50, th0 - 0.06 * U) or chime >= 0.34
            if wake:
                wakes[m].append(ts)
                if m in ("M1", "A"): state[m]["soc"] = max(22.0, state[m]["soc"] - 22.0)
                if m in ("M2", "A"): state[m]["U"] *= 0.2
            if actual:
                actual_count += 1
                hit[m] += 1 if wake else 0
                miss[m] += 0 if wake else 1
            elif wake:
                fp[m] += 1

    def stats(m: str) -> dict[str, Any]:
        w = wakes[m]
        gaps = [(w[i] - w[i - 1]) / 1000 for i in range(1, len(w))]
        import statistics
        bursts, cur = [], 1
        for i in range(1, len(w)):
            if (w[i] - w[i - 1]) / 1000 <= 60: cur += 1
            else: bursts.append(cur); cur = 1
        if w: bursts.append(cur)
        return {"wakes": len(w),
                "median_gap_s": round(statistics.median(gaps), 0) if gaps else None,
                "max_silence_s": round(max(gaps), 0) if gaps else None,
                "max_burst": max(bursts) if bursts else 0,
                "recall": round(hit[m] / max(1, actual_count), 2),
                "false_wakes": fp[m],
                "threshold0": th0}

    report = {"window_messages": len(rows), "actual_turns": actual_count,
              "probes": len(chords), "chat": CHAT,
              "M1": stats("M1"), "M2": stats("M2"), "A": stats("A")}
    Path("/tmp/wake_compare_full.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
