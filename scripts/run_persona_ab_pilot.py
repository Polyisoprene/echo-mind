#!/usr/bin/env python
"""Run the 6-scenario D14 pilot against the configured LLM (12 calls)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import load_config_from_json

ROOT = Path(__file__).resolve().parents[1]


def _content(resp: dict[str, Any]) -> str:
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message")
    return str(message.get("content") or "") if isinstance(message, dict) else ""


async def main() -> int:
    prompts = json.loads(
        (ROOT / "reports" / "persona_placement_prompts.json").read_text(encoding="utf-8")
    )
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    db = SqliteDatabase(Path(tempfile.mkdtemp()) / "ab.db")
    await db.initialize()
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    rows: list[dict[str, Any]] = []
    for scenario in prompts:
        for variant in ("A_user", "B_system"):
            resp = await llm.complete(
                scenario[variant], temperature=0.6, max_tokens=400, chat_key="ab:pilot"
            )
            rows.append({
                "scenario": scenario["scenario"], "variant": variant,
                "must_reply": scenario["must_reply"],
                "reply": _content(resp),
            })
    out = ROOT / "reports" / "persona_placement_pilot.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in rows:
        print(f"[{row['scenario']}/{row['variant']}] {row['reply'][:60]!r}")
    print(f"wrote {len(rows)} replies to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
