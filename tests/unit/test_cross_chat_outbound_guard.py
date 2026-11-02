"""Cross-chat sends still go through the outbound sanitizer/counter."""

from __future__ import annotations

from typing import cast

from echomind.runtime.agent_runner import AgentSessionRunner


class _Noop:
    pass


def _runner() -> AgentSessionRunner:
    runner = cast(AgentSessionRunner, _Noop())
    runner._bans = {}
    return runner


def test_send_to_chat_is_counted_and_guarded() -> None:
    runner = _runner()
    sent: list[str] = []
    args, error = AgentSessionRunner._prepare_outbound_args(
        runner, "private:1", "send_to_chat",
        {"target_chat_key": "group:2", "messages": ["去群里说"]}, sent,
    )
    assert error == ""
    assert args is not None
    assert sent == ["去群里说"]
    blocked, message = AgentSessionRunner._prepare_outbound_args(
        runner, "private:1", "send_to_chat",
        {"target_chat_key": "group:2", "messages": ["再说一次"]}, sent,
    )
    assert blocked is None
    assert "重复" in message
