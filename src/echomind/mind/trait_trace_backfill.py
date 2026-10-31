"""P0 backfill candidates from real turn traces; one independent context per day."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

DAY_MS = 86_400_000


@dataclass(frozen=True)
class TraceEvidenceCandidate:
    turn_id: str
    chat_key: str
    event_ms: int
    quote: str
    context_hash: str


def _tool_text(step: Any) -> str:
    if not isinstance(step, dict):
        return ""
    name = str(step.get("name") or "")
    if not name.startswith(("send_message", "feiyu_say", "feiyu_cover")):
        return ""
    try:
        detail = json.loads(str(step.get("detail") or "{}"))
    except json.JSONDecodeError:
        return ""
    for key in ("rescued", "text", "message"):
        text = str(detail.get(key) or "").strip()
        if text:
            return text
    return ""




def _sent_text(steps: list[Any]) -> str:
    """Only actual sent text (send_message/feiyu_*); never internal thoughts."""
    for step in reversed(steps):
        text = _tool_text(step)
        if text:
            return text
    return ""


def _llm_output(steps_json: str) -> str:
    try:
        steps = json.loads(steps_json)
    except json.JSONDecodeError:
        return ""
    return _sent_text(steps) if isinstance(steps, list) else ""


def candidates_from_rows(
    rows: Iterable[Any], existing_days: set[int],
) -> tuple[TraceEvidenceCandidate, ...]:
    """Dedupe by UTC day; keep the latest real assistant output of that day."""
    by_day: dict[int, TraceEvidenceCandidate] = {}
    for row in rows:
        event_ms = int(row["ts"])
        day = event_ms // DAY_MS
        if day in existing_days:
            continue
        quote = _llm_output(str(row["steps_json"]))
        if not quote:
            continue
        by_day[day] = TraceEvidenceCandidate(
            turn_id=str(row["turn_id"]), chat_key=str(row["chat_key"]),
            event_ms=event_ms, quote=quote,
            context_hash=hashlib.sha256(
                f"{row['chat_key']}||{day}".encode()
            ).hexdigest(),
        )
    return tuple(sorted(by_day.values(), key=lambda item: item.event_ms))
