"""Narrow port for generated trait candidates.

Status: designed, not yet wired into production. `SqliteTraitCandidateStore`
implements this shape and is exercised only by tests today; no runtime call
site writes or promotes candidates. This matches `CAP-TRAIT-GROWTH = partial`
in docs/capabilities.json ("自动 support/candidate 流仍稀疏"). Keep the port:
it records the intended seam for finishing that capability.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from echomind.domain.trait_candidate import TraitCandidate


@runtime_checkable
class ITraitCandidateStore(Protocol):
    async def save_candidate(self, candidate: TraitCandidate) -> None: ...

    async def list_candidates(
        self, trait_id: int, limit: int = 20
    ) -> tuple[TraitCandidate, ...]: ...

    async def get_candidate(self, candidate_id: int) -> TraitCandidate | None: ...

    async def promote_candidate(
        self, candidate_id: int, approved_by: str, reason: str
    ) -> bool: ...
