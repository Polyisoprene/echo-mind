"""Narrow port for append-only trait evidence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from echomind.domain.trait_evidence import TraitEvidence


@runtime_checkable
class ITraitEvidenceStore(Protocol):
    """Persist and read trait evidence; implementers own dedupe/ordering."""

    async def record_trait_evidence(self, evidence: TraitEvidence) -> None: ...

    async def list_trait_evidence(
        self, trait_id: int, limit: int = 50
    ) -> tuple[TraitEvidence, ...]: ...

    async def refresh_lifecycle(self, trait_id: int) -> str: ...
