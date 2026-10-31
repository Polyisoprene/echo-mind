"""Narrow port for generated trait candidates."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from echomind.domain.trait_candidate import TraitCandidate


@runtime_checkable
class ITraitCandidateStore(Protocol):
    async def save_candidate(self, candidate: TraitCandidate) -> None: ...

    async def list_candidates(
        self, trait_id: int, limit: int = 20
    ) -> tuple[TraitCandidate, ...]: ...
