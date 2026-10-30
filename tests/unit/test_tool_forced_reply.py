"""Stage 41: a model that forgets the tool call must be forced to call send_message."""

from __future__ import annotations

from typing import Any

from echomind.runtime.tool_forced_reply import FORCE_INSTRUCTION, force_send_call


class _Llm:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}
        self.messages: list[dict[str, Any]] = []

    async def complete(self, messages: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
        self.messages, self.kwargs = messages, kw
        return {"choices": [{"message": {"tool_calls": [{"id": "1"}]}}]}


async def test_force_send_forces_send_message_tool() -> None:
    llm = _Llm()
    await force_send_call(llm, [{"role": "user", "content": "hi"}], [{"type": "function"}], "g")
    assert llm.kwargs["tool_choice"]["function"]["name"] == "send_message"
    assert llm.messages[-1]["content"] == FORCE_INSTRUCTION
