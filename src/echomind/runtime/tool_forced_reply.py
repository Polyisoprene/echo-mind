"""Stage 41: when the model forgets to call send_message, force a tool call instead of
shipping raw text (which can be inner monologue)."""

from __future__ import annotations

from typing import Any

FORCE_INSTRUCTION = (
    "系统：你刚才只输出了文字，没有调用发送工具。"
    "现在请立刻调用 send_message，把你真正想对群里说的话发出去；不要只回复文字。"
)
FORCE_CHOICE: dict[str, Any] = {"type": "function", "function": {"name": "send_message"}}


async def force_send_call(
    llm: Any, messages: list[dict[str, Any]], tools_schema: list[dict[str, Any]] | None,
    chat_key: str,
) -> dict[str, Any]:
    """One repair round that must produce a send_message tool call."""
    msgs = [*messages, {"role": "user", "content": FORCE_INSTRUCTION}]
    resp: dict[str, Any] = await llm.complete(
        msgs, tools=tools_schema, temperature=0.4, max_tokens=1200,
        chat_key=chat_key, tool_choice=FORCE_CHOICE,
    )
    return resp
