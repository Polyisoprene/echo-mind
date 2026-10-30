"""Stage 41: turn-step helpers extracted from the runner (kept out of the 300-line cap)."""

from __future__ import annotations

import json
from typing import Any

from echomind.domain.models import TurnStep


def _extract_assistant_msg(raw_resp: dict[str, Any]) -> dict[str, Any]:
    choices = raw_resp.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    msg = first.get("message", {}) if isinstance(first, dict) else {}
    return msg if isinstance(msg, dict) else {}


def _parse_tool_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if not isinstance(raw_args, str):
        return {}
    try:
        parsed: dict[str, Any] = json.loads(raw_args)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _llm_step(resp: dict[str, Any], elapsed_ms: int, seq: int) -> TurnStep:
    usage = resp.get("usage")
    info = usage if isinstance(usage, dict) else {}
    prompt = int(info.get("prompt_tokens", 0) or 0)
    completion = int(info.get("completion_tokens", 0) or 0)
    details = info.get("prompt_tokens_details")
    cached = int(details.get("cached_tokens", 0) or 0) if isinstance(details, dict) else 0
    detail = f"{prompt}→{completion} tok" + (f"（缓存 {cached}）" if cached else "")
    out = str(_extract_assistant_msg(resp).get("content") or "").strip()[:300]
    return TurnStep(
        seq=seq, kind="llm", name=str(resp.get("model") or ""),
        detail=detail, output=out, elapsed_ms=elapsed_ms,
    )


def _tool_step(
    name: str, args: dict[str, Any], result_str: str, elapsed_ms: int, seq: int
) -> TurnStep:
    snippet = json.dumps(args, ensure_ascii=False)[:240]
    return TurnStep(
        seq=seq, kind="tool", name=name, detail=snippet,
        output=result_str[:300], elapsed_ms=elapsed_ms,
    )


def _tool_reply(tc: dict[str, Any], name: str, content: str) -> dict[str, Any]:
    return {
        "role": "tool", "tool_call_id": str(tc.get("id", "call_1")),
        "name": name, "content": content,
    }




def has_tool_calls(raw_calls: Any) -> bool:
    """True only for a non-empty list of tool calls."""
    return isinstance(raw_calls, list) and bool(raw_calls)


def tool_call_list(raw_calls: Any) -> list[Any]:
    """Narrow a tool_calls payload to a list for the executor."""
    return raw_calls if isinstance(raw_calls, list) else []
