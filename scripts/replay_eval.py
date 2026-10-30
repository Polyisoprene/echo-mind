#!/usr/bin/env python
"""A-lane deterministic replay evaluation (Stage 28 AB-01/AB-02, RGR-07).

Replays real group messages through the live cognitive facade using recorded 6D chords
(no LLM calls), and emits a machine-readable metrics report for the A->B promotion gate.

Usage:
    uv run python scripts/replay_eval.py \
        --db data/replay-snapshot.db --fixture tests/fixtures/chords_stage28.json \
        --chat-key group:10002002 --owner 10001001 --turns 200 --out reports/
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import echomind.mind.facade as facade_mod  # noqa: E402
import echomind.mind.subconscious_probe as probe_mod  # noqa: E402
from echomind.core.bootstrap import EchoMindContainer  # noqa: E402
from echomind.domain.models import Percept, TurnOutcome  # noqa: E402
from echomind.mind.chord_replay import ChordFixtureProbe  # noqa: E402
from echomind.mind.plasticity import compute_turn_social_reward  # noqa: E402

_TENSOR_MIDS: set[str] = set()
_FRAME_MIDS: set[str] = set()
_REWARDS: list[float] = []
_CLOCK_BASE = 1_770_000_000_000


class _FrozenClock:
    """Advance a deterministic wall clock so replays are reproducible."""

    def __init__(self, base_ms: int, step_ms: int = 1_000) -> None:
        self._ms = base_ms
        self._step = step_ms

    def install(self) -> None:
        clock = self

        def _now() -> float:
            clock._ms += clock._step
            return clock._ms / 1000.0

        time.time = _now  # type: ignore[assignment]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _load_messages(db: Path, chat_key: str, limit: int) -> list[tuple[int, int, str, str, str]]:
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT id, ts, sender_id, sender_name, text FROM chat_messages "
            "WHERE chat_key = ? AND is_self = 0 ORDER BY ts ASC, id ASC LIMIT ?",
            (chat_key, limit),
        ).fetchall()
    finally:
        conn.close()
    return [(int(r[0]), int(r[1]), str(r[2]), str(r[3] or r[2]), str(r[4] or "")) for r in rows]


def _bonds(db: Path, chat_key: str) -> dict[str, tuple[float, float]]:
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT user_id, affinity_score, trust_score FROM social_bonds WHERE chat_key = ?",
            (chat_key,),
        ).fetchall()
    finally:
        conn.close()
    return {str(r[0]): (float(r[1]), float(r[2])) for r in rows}


def _instrument() -> None:
    original_tensor = probe_mod.apply_chord_tensor_to_snapshot
    original_reward = facade_mod.apply_chord_reward

    def tensor_spy(*args: Any, **kwargs: Any) -> Any:
        out = original_tensor(*args, **kwargs)
        _TENSOR_MIDS.add(str(getattr(args[2], "message_id", "")))
        return out

    def reward_spy(*args: Any, **kwargs: Any) -> Any:
        outcome, chord = original_reward(*args, **kwargs)
        _REWARDS.append(float(outcome.social_reward))
        return outcome, chord

    probe_mod.apply_chord_tensor_to_snapshot = tensor_spy
    facade_mod.apply_chord_reward = reward_spy


async def _replay(args: argparse.Namespace, work_db: Path) -> dict[str, Any]:
    container = await EchoMindContainer.create(
        db_path=work_db, operator_ids=(args.owner,) if args.owner else (),
        default_chat_key=args.chat_key
    )
    facade = container.cognitive_facade
    probe = ChordFixtureProbe(args.fixture)
    facade.set_subconscious_probe(probe)  # type: ignore[arg-type]

    messages = _load_messages(work_db, args.chat_key, args.turns)
    before = _bonds(work_db, args.chat_key)
    wakes, cooldown, cache_peak = 0, 0, 0
    for mid, ts, uid, name, text in messages:
        percept = Percept(
            chat_key=args.chat_key, scene="private" if "private:" in args.chat_key else "group",
            message_id=str(mid), timestamp_ms=ts, sender_id=uid, sender_name=name, text=text,
        )
        dec = await facade.evaluate_incoming(percept)
        cache_peak = max(cache_peak, len(facade._chord_cache))
        if "冷却" in dec.reason:
            cooldown += 1
        if not dec.should_wake:
            continue
        wakes += 1
        _FRAME_MIDS.add(str(mid))
        await facade.build_cognitive_frame(args.chat_key, (percept,))
        production_reward = compute_turn_social_reward(
            text, is_poke=False, is_owner=bool(args.owner and uid == args.owner)
        )
        await facade.on_turn_completed(
            TurnOutcome(
                session_id=f"replay-{mid}", chat_key=args.chat_key, triggers=(percept,),
                sent_texts=("（replay）",), social_reward=production_reward,
            )
        )
    after = _bonds(work_db, args.chat_key)
    _ = container
    deltas: dict[str, dict[str, float]] = {}
    for uid in set(before) | set(after):
        base = before.get(uid, (30.0, 0.75))
        cur = after.get(uid, base)
        deltas[uid] = {
            "affinity": round(cur[0] - base[0], 2),
            "trust": round(cur[1] - base[1], 3),
        }
    double_apply = len(_TENSOR_MIDS & _FRAME_MIDS)
    spread = round(max(_REWARDS) - min(_REWARDS), 3) if len(_REWARDS) > 1 else 0.0
    return {
        "chat_key": args.chat_key,
        "turns": len(messages),
        "wakes": wakes,
        "cooldown_blocks": cooldown,
        "probe_calls": probe.calls,
        "cache_peak": cache_peak,
        "cache_limit_ok": cache_peak <= 256,
        "double_apply": double_apply,
        "reward_samples": len(_REWARDS),
        "reward_spread": spread,
        "bond_deltas": deltas,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="A-lane deterministic replay evaluation")
    ap.add_argument("--db", default="data/replay-snapshot.db")
    ap.add_argument("--work-db", default="data/a-sandbox.db")
    ap.add_argument("--fixture", default="tests/fixtures/chords_stage28.json")
    ap.add_argument("--chat-key", default="group:10002002")
    ap.add_argument("--owner", default="")
    ap.add_argument("--turns", type=int, default=200)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    source = Path(args.db)
    if not source.is_file():
        print(f"[replay] missing snapshot db: {source}", file=sys.stderr)
        return 2
    work_db = Path(args.work_db)
    work_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, work_db)

    _FrozenClock(_CLOCK_BASE).install()
    _instrument()
    metrics = asyncio.run(_replay(args, work_db))
    metrics["source_db"] = str(source)
    metrics["source_sha256_16"] = _sha256(source)
    metrics["work_db"] = str(work_db)
    metrics["ts"] = _CLOCK_BASE
    metrics["partial"] = False

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"replay_{metrics['ts']}.json"
    report.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"[replay] report -> {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
