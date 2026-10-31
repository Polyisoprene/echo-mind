"""Stage 43: configurable token budgets and truncation detection for Qzone/proactive calls."""

from __future__ import annotations

from typing import Any


def extract_content(resp: dict[str, Any]) -> str:
    """Read the assistant text out of a chat-completions response."""
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    raw_msg = first.get("message")
    msg = raw_msg if isinstance(raw_msg, dict) else {}
    return str(msg.get("content") or "").strip().strip('"“”')


def budget(cfg: dict[str, str], key: str, fallback: int) -> int:
    """Read a token budget from skill config, clamped to a sane minimum."""
    try:
        return max(60, int(cfg.get(key, fallback)))
    except (TypeError, ValueError):
        return fallback


def is_truncated(resp: dict[str, Any]) -> bool:
    """True when the provider cut generation at the token limit."""
    choices = resp.get("choices") or []
    return bool(choices) and str(choices[0].get("finish_reason") or "") == "length"
