"""M4.2 5-Stage Safety Reply Rescue Policy when LLM forgets to call send_message."""

from __future__ import annotations

import re

THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>[\s\S]*?</think>", re.IGNORECASE)
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
META_MONOLOGUE_RE = re.compile(
    r"用户|群友|模型|工具|调用|回复策略|不需要回复|保持沉默|无需回应|从上下文看|作为AI|无需插话|不作回应"
)


def _strip_reasoning_and_fences(raw_content: str) -> str:
    no_think = THINK_BLOCK_RE.sub("", raw_content)
    return CODE_FENCE_RE.sub("", no_think).strip()


def rescue_unsent_reply(raw_content: str) -> str | None:
    """Rescue a clean single-line spoken reply when LLM forgot to invoke send_message."""
    cleaned = _strip_reasoning_and_fences(raw_content)
    if not cleaned:
        return None
    if len(cleaned) > 120 or "\n" in cleaned:
        return None
    if cleaned.startswith(("{", "[", "<tool_call", "```")):
        return None
    if META_MONOLOGUE_RE.search(cleaned):
        return None
    return cleaned
