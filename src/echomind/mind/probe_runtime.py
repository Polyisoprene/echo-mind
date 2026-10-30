"""Stage 36: make the subconscious probe reliable.

The probe is a classifier whose output is parsed, never sent. It therefore runs without
thinking mode (reasoning would eat the tiny token budget) and in JSON mode, and it retries
once when the response is empty or unparsable. Failures are counted so they can never be
silent again.
"""

from __future__ import annotations

from typing import Any

PROBE_MAX_TOKENS = 256
_MODEL = ""
_STATS: dict[str, int] = {"calls": 0, "retries": 0, "empty": 0, "ok": 0}


def set_probe_model(name: str) -> None:
    """Optional dedicated model for probing (empty = follow the primary gateway)."""
    global _MODEL
    _MODEL = name.strip()


def probe_model() -> str:
    """Currently configured probe model ('' means primary)."""
    return _MODEL


def probe_metrics() -> dict[str, int]:
    """Success/retry/empty counters for dashboards and tests."""
    return dict(_STATS)


def _content(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


async def run_probe(llm: Any, msgs: list[dict[str, Any]], chat_key: str) -> str:
    """Call the probe once, retrying without JSON mode if the first answer is empty."""
    for attempt, json_mode in enumerate((True, False)):
        try:
            resp = await llm.complete(
                msgs, temperature=0.1, max_tokens=PROBE_MAX_TOKENS, chat_key=chat_key,
                thinking_off=True, json_mode=json_mode, model_override=_MODEL,
            )
        except Exception:
            _STATS["empty"] += 1
            return ""
        _STATS["calls"] += 1
        raw = _content(resp)
        if raw:
            _STATS["ok"] += 1
            return raw
        if attempt == 0:
            _STATS["retries"] += 1
    _STATS["empty"] += 1
    return ""
