"""M4.2 5-Stage Safety Reply Rescue Policy when LLM forgets to call send_message."""

from __future__ import annotations

import re

THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>[\s\S]*?</think>", re.IGNORECASE)
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
PAREN_BLOCK_RE = re.compile(r"^[（(][\s\S]*?[）)]\s*$")
LEADING_PAREN_RE = re.compile(r"^\s*[（(][^）)\n]{1,60}[）)]\s*")
META_MONOLOGUE_RE = re.compile(
    r"用户|群友|模型|工具|调用|回复策略|不需要回复|保持沉默|无需回应|从上下文看|"
    r"作为AI|无需插话|不作回应|不插话|不插嘴|保持安静|先不打扰|不用回|这轮没|没点我"
)


def _strip_reasoning_and_fences(raw_content: str) -> str:
    no_think = THINK_BLOCK_RE.sub("", raw_content)
    no_fence = CODE_FENCE_RE.sub("", no_think).strip()
    if PAREN_BLOCK_RE.match(no_fence):
        return ""
    return LEADING_PAREN_RE.sub("", no_fence).strip()


def _is_inner_monologue(cleaned: str) -> bool:
    """Treat any parenthesis/bracket residue as reasoning noise instead of spoken text."""
    if "（" in cleaned or "(" in cleaned or "）" in cleaned or ")" in cleaned:
        return True
    return META_MONOLOGUE_RE.search(cleaned) is not None


def rescue_unsent_reply(raw_content: str, *, must_reply: bool = True) -> str | None:
    """Rescue a clean single-line spoken reply when LLM forgot to invoke send_message."""
    cleaned = _strip_reasoning_and_fences(raw_content)
    if not cleaned or len(cleaned) > 120 or "\n" in cleaned:
        return None
    if cleaned.startswith(("{", "[", "<tool_call", "```")):
        return None
    if _is_inner_monologue(cleaned):
        return None
    if not must_reply and ("（" in raw_content or "(" in raw_content):
        return None
    return cleaned
