#!/usr/bin/env python
"""Score the D14 pilot: must-reply success and malformed tool-only replies."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _is_malformed(reply: str) -> bool:
    body = reply.strip()
    return body.startswith("<tool_call>") and "<send_message>" not in body


def _answered(reply: str) -> bool:
    body = reply.strip()
    return bool(body) and ("<send_message>" in body or not _is_malformed(body))


def main() -> int:
    rows = json.loads(
        (ROOT / "reports" / "persona_placement_pilot.json").read_text(encoding="utf-8")
    )
    report: dict[str, dict[str, object]] = {}
    for variant in ("A_user", "B_system"):
        picked = [r for r in rows if r["variant"] == variant]
        must = [r for r in picked if r["must_reply"]]
        report[variant] = {
            "scenarios": len(picked),
            "must_reply_total": len(must),
            "must_reply_answered": sum(_answered(r["reply"]) for r in must),
            "malformed_tool_only": sum(_is_malformed(r["reply"]) for r in picked),
            "empty": sum(not r["reply"].strip() for r in picked),
        }
    out = ROOT / "reports" / "persona_placement_pilot_score.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for variant, data in report.items():
        print(variant, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
