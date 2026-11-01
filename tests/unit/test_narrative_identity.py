"""Narrative projection is evidence-bound and active-only."""

from __future__ import annotations

from typing import cast

import pytest

from echomind.domain.models import PersonaTrait
from echomind.domain.ports import IWorkingStateStore
from echomind.domain.trait_evidence import TraitEvidence
from echomind.domain.trait_evidence_ports import ITraitEvidenceStore
from echomind.mind.narrative_identity import build_narrative


class _Work:
    async def sync_persona_traits(self) -> tuple[PersonaTrait, ...]:
        return (
            PersonaTrait(trait_id=1, trait_text="会看图", status="active"),
            PersonaTrait(trait_id=2, trait_text="旧习惯", status="legacy_unverified"),
        )


class _Evidence:
    async def list_trait_evidence(
        self, trait_id: int, limit: int = 50,
    ) -> tuple[TraitEvidence, ...]:
        return (TraitEvidence(
            trait_id=trait_id, session_id="s", turn_id="t", quote="真实原话",
            quote_kind="assistant", polarity=1, context_hash="c", created_ms=1,
        ),)


@pytest.mark.asyncio
async def test_narrative_uses_only_active_traits_and_quotes() -> None:
    narrative = await build_narrative(
        cast(IWorkingStateStore, _Work()), cast(ITraitEvidenceStore, _Evidence()),
    )
    assert narrative.trait_ids == (1,)
    assert "会看图" in narrative.lines[0]
    assert "真实原话" in narrative.lines[0]
    assert "旧习惯" not in "".join(narrative.lines)
