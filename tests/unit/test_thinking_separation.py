"""Stage 32 (plan C): reasoning must travel in its own channel, never in the sent text."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import GatewayEndpointConfig
from echomind.runtime.reply_rescue import rescue_unsent_reply


class _Capture:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    async def post_json(self, url: str, headers: dict[str, str], payload: dict[str, object],
                        timeout: float) -> dict[str, object]:  # noqa: ASYNC109 - mirrors transport
        _ = (url, headers, timeout)
        self.payloads.append(payload)
        return {"choices": [{"message": {"content": ""}}], "usage": {}}


def _gw() -> GatewayEndpointConfig:
    return GatewayEndpointConfig(name="p", base_url="https://x", api_key="k", model="m",
                                 timeout_ms=1000)


_DB = SqliteDatabase(Path(tempfile.gettempdir()) / "s32_thinking.db")


def _db() -> SqliteDatabase:
    return _DB


def _complete_kwargs() -> dict[str, object]:
    return {"messages": [{"role": "user", "content": "hi"}], "tools": None}


@pytest.fixture(autouse=True)
async def _schema() -> None:
    await _DB.initialize()


async def test_thinking_is_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ECHOMIND_THINKING", raising=False)
    cap = _Capture()
    gw = FailoverLlmGateway(_gw(), _gw(), _db(), transport=cap)
    await gw.complete(**_complete_kwargs())  # type: ignore[arg-type]
    assert cap.payloads[-1]["thinking"] == {"type": "enabled"}
    assert cap.payloads[-1]["reasoning_effort"] == "low"


async def test_thinking_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECHOMIND_THINKING", "off")
    cap = _Capture()
    gw = FailoverLlmGateway(_gw(), _gw(), _db(), transport=cap)
    await gw.complete(**_complete_kwargs())  # type: ignore[arg-type]
    assert "thinking" not in cap.payloads[-1]


def test_reasoning_only_response_is_not_sent() -> None:
    """If the model only produced reasoning, there is nothing to rescue."""
    assert rescue_unsent_reply("") is None
