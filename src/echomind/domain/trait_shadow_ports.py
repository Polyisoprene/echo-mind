"""Narrow ports for the P4b shadow decision log."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from echomind.domain.models import PersonaTrait
from echomind.domain.trait_shadow_record import TraitShadowRecord


@runtime_checkable
class IActiveTraitReader(Protocol):
    async def active_traits(self) -> tuple[PersonaTrait, ...]: ...


@runtime_checkable
class ITraitShadowStore(Protocol):
    async def record_shadow(self, record: TraitShadowRecord) -> None: ...

    async def list_shadow(
        self, chat_key: str, limit: int = 50
    ) -> tuple[TraitShadowRecord, ...]: ...
