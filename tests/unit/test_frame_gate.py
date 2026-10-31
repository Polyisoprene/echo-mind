"""P3.3b: the frame gate drops private/secret memories and logs the refusal."""

from __future__ import annotations

from typing import Any, Literal, cast

import pytest

from echomind.domain.models import SemanticFact
from echomind.domain.ports import IDisclosureLog
from echomind.mind.facade_memory import gate_frame


class _Log:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def log_disclosure(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)

    async def has_grant(self, **kwargs: Any) -> bool:
        return False


def _fact(
    sensitivity: Literal["public", "group", "private", "secret"],
    owner: str = "L",
) -> SemanticFact:
    return SemanticFact(
        fact_id=1, chat_key="group:1", subject="x", fact_text="y",
        scope="person", owner_id=owner, sensitivity=sensitivity,
    )


@pytest.mark.asyncio
async def test_private_fact_is_dropped_without_the_owner() -> None:
    log = _Log()
    kept, _ = await gate_frame((_fact("private"),), (), frozenset({"M"}), "group:1",
                               cast(IDisclosureLog, log))
    assert kept == ()
    assert log.calls[0]["reason"] == "owner_absent"
    assert log.calls[0]["action"] == "keep"


@pytest.mark.asyncio
async def test_private_fact_passes_with_the_owner_and_secret_never() -> None:
    log = _Log()
    kept, _ = await gate_frame((_fact("private"),), (), frozenset({"L"}), "group:1",
                               cast(IDisclosureLog, log))
    assert len(kept) == 1
    assert log.calls[-1]["action"] == "say", "the included person fact is logged"

    kept, _ = await gate_frame((_fact("secret"),), (), frozenset({"L"}), "group:1",
                               cast(IDisclosureLog, log))
    assert kept == ()
    assert log.calls[-1]["reason"] == "secret_without_grant"
