#!/usr/bin/env python
"""Run warm/offense/mixed synthetic streams and report trait + shadow stats."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.persona_layer_repo import SqlitePersonaLayerStore
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.persona_dynamics import TRAIT_MAX_DEVIATION
from echomind.mind.plasticity import PARAM_BASELINES, NeuroplasticityEngine
from echomind.mind.trait_shadow_service import TraitShadowService

ROOT = Path(__file__).resolve().parents[1]
BASE = 1_700_000_000_000
DAY = 86_400_000
WARM_QUOTE = "我看到图里那个小槽点了"
OFFENSE_QUOTE = "别用命令语气使唤我"


def _outcome(day: int, *, warm: bool) -> TurnOutcome:
    event_ms = BASE + day * DAY
    percept = Percept(
        chat_key="g", scene="group", message_id=f"m{day}", timestamp_ms=event_ms,
        sender_id="u1", sender_name="U", text="发图" if warm else "命令",
    )
    # Odd warm days carry a tool-only evidence row, so action eligibility can see it.
    tool_only = warm and day % 2 == 0
    return TurnOutcome(
        session_id=f"turn-{day}", chat_key="g", triggers=(percept,),
        sent_texts=() if tool_only else (WARM_QUOTE if warm else OFFENSE_QUOTE,),
        tools_used=("look_at_image",) if warm else (),
        social_reward=0.8 if warm else -0.8,
    )


async def run_stream(name: str, days: int, db_path: Path) -> dict[str, Any]:
    db = SqliteDatabase(db_path)
    await db.initialize()
    working = SqliteWorkingStateStore(db)
    await working.ensure_default_params()
    layers = SqlitePersonaLayerStore(db)
    await layers.ensure_schema()
    evidence = SqliteTraitEvidenceStore(db)
    shadow_store = SqliteTraitShadowStore(db)
    shadow = TraitShadowService(shadow_store, evidence, shadow_store)
    engine = NeuroplasticityEngine(working, layers, evidence_store=evidence)
    for day in range(1, days + 1):
        warm = (day % 2 == 0) if name == "mixed" else (name == "warm")
        event = _outcome(day, warm=warm)
        await engine.adapt_from_outcome(event, now_ms=BASE + day * DAY)
        await engine.settle_baseline(BASE + (day + 1) * DAY)
        await shadow.record(event)
    active = await shadow_store.active_traits()
    params = await working.get_plastic_params()
    drifts = [
        abs(spec.value - PARAM_BASELINES[key])
        for key, spec in params.items() if key in PARAM_BASELINES
    ]
    rows = await shadow_store.list_shadow("g", days + 1)
    allowed = sorted({tool for row in rows for tool in row.allowed_tools})
    actual = sorted({tool for row in rows for tool in row.actual_tools})
    return {
        "active_traits": [
            {"id": trait.trait_id, "category": trait.category, "text": trait.trait_text}
            for trait in active
        ],
        "shadow_rows": len(rows),
        "allowed_tools": allowed,
        "actual_tools": actual,
        "allow_refusal_rows": sum(row.allow_refusal for row in rows),
        "max_param_drift": round(max(drifts, default=0.0), 3),
        "edge": round(TRAIT_MAX_DEVIATION, 3),
    }


async def _stream(name: str, days: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        return await run_stream(name, days, Path(tmp) / "replay.db")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "persona_replay.json")
    args = parser.parse_args()
    report = {name: await _stream(name, args.days) for name in ("warm", "offense", "mixed")}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
