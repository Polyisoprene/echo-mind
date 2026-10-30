"""Stage 36: the probe must never fail silently (empty content, truncation, retry)."""

from __future__ import annotations

from typing import Any

import pytest

from echomind.mind import probe_runtime


class _Llm:
    def __init__(self, replies: list[dict[str, Any]]) -> None:
        self._replies = replies
        self.calls: list[dict[str, Any]] = []

    async def complete(self, messages: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
        self.calls.append(kw)
        empty = {"choices": [{"message": {"content": ""}}]}
        return self._replies.pop(0) if self._replies else empty


def _msg() -> dict[str, Any]:
    return {"choices": [{"message": {"content": '{"role":"direct_to_me","topic_pull":2}'}}]}


@pytest.mark.asyncio
async def test_probe_disables_thinking_and_uses_json_mode() -> None:
    llm = _Llm([_msg()])
    raw = await probe_runtime.run_probe(llm, [{"role": "user", "content": "x"}], "subconscious:g")
    assert "direct_to_me" in raw
    assert llm.calls[0]["thinking_off"] is True
    assert llm.calls[0]["json_mode"] is True
    assert llm.calls[0]["max_tokens"] == probe_runtime.PROBE_MAX_TOKENS


@pytest.mark.asyncio
async def test_empty_content_retries_once_without_json_mode() -> None:
    empty = {"choices": [{"message": {"content": ""}}]}
    llm = _Llm([empty, _msg()])
    raw = await probe_runtime.run_probe(llm, [{"role": "user", "content": "x"}], "subconscious:g")
    assert "direct_to_me" in raw
    assert len(llm.calls) == 2 and llm.calls[1]["json_mode"] is False


@pytest.mark.asyncio
async def test_two_empty_answers_are_counted_as_failure() -> None:
    empty = {"choices": [{"message": {"content": ""}}]}
    llm = _Llm([empty, empty])
    before = probe_runtime.probe_metrics()["empty"]
    raw = await probe_runtime.run_probe(llm, [{"role": "user", "content": "x"}], "subconscious:g")
    assert raw == ""
    assert probe_runtime.probe_metrics()["empty"] == before + 1


def test_probe_model_is_configurable() -> None:
    probe_runtime.set_probe_model("deepseek-v4.1-flash-free")
    assert probe_runtime.probe_model() == "deepseek-v4.1-flash-free"
    probe_runtime.set_probe_model("")
