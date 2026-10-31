"""Narrow lookup for memories that carry an exact source quote."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IMemoryQuoteLookup(Protocol):
    async def semantic_ids(self, chat_key: str, quote: str) -> tuple[int, ...]: ...

    async def episodic_ids(self, chat_key: str, quote: str) -> tuple[int, ...]: ...
