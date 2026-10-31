"""D9: a reply that overlaps an included person fact is logged as said."""

from __future__ import annotations

from typing import Any, cast

import pytest

from echomind.domain.ports import IDisclosureLog
from echomind.mind.facade_memory import attribute_reply


class _Log:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def log_disclosure(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_overlap_logs_said_with_post_phase() -> None:
    log = _Log()
    included = ((1, "L 的病", "最近在休养"),)
    await attribute_reply(
        "L 的病最近在休养，别担心", included, "group:1", "M",
        cast(IDisclosureLog, log),
    )
    assert log.calls[0]["action"] == "said"
    assert log.calls[0]["phase"] == "post"
    assert log.calls[0]["audience"] == ("M",)


@pytest.mark.asyncio
async def test_unrelated_reply_does_not_log() -> None:
    log = _Log()
    await attribute_reply(
        "今天天气不错", ((1, "L 的病", "最近在休养"),), "group:1", "M",
        cast(IDisclosureLog, log),
    )
    assert not log.calls
