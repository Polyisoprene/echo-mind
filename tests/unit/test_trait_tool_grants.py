"""Live trait grants are additive and never remove base tools."""

from __future__ import annotations

from typing import cast

import pytest

from echomind.domain.models import CyberneticCoreState, PersonaTrait
from echomind.domain.ports import IWorkingStateStore
from echomind.domain.trait_evidence import TraitEvidence
from echomind.domain.trait_evidence_ports import ITraitEvidenceStore
from echomind.mind.trait_tool_grants import apply_live_grants


class _Working:
    def __init__(self, traits: tuple[PersonaTrait, ...]) -> None:
        self._traits = traits

    async def sync_persona_traits(self) -> tuple[PersonaTrait, ...]:
        return self._traits


class _Evidence:
    def __init__(self, rows: dict[int, tuple[TraitEvidence, ...]]) -> None:
        self._rows = rows

    async def list_trait_evidence(
        self, trait_id: int, limit: int = 50,
    ) -> tuple[TraitEvidence, ...]:
        return self._rows.get(trait_id, ())


def _evidence(trait_id: int, tool: str) -> TraitEvidence:
    return TraitEvidence(
        trait_id=trait_id, session_id="s", turn_id="t", quote=tool,
        quote_kind="tool", polarity=1, context_hash="c", created_ms=1,
    )


@pytest.mark.asyncio
async def test_tool_grant_is_added_not_substituted() -> None:
    core = CyberneticCoreState(selected_tools=("send_message",))
    trait = PersonaTrait(trait_id=1, trait_text="会看图", status="active")
    result = await apply_live_grants(
        core, cast(IWorkingStateStore, _Working((trait,))),
        cast(ITraitEvidenceStore, _Evidence({1: (_evidence(1, "look_at_image"),)})),
    )
    assert result.selected_tools == ("send_message", "look_at_image")


@pytest.mark.asyncio
async def test_no_tool_evidence_leaves_tools_unchanged() -> None:
    core = CyberneticCoreState(selected_tools=("send_message",))
    trait = PersonaTrait(trait_id=1, trait_text="只说话", status="active")
    result = await apply_live_grants(
        core, cast(IWorkingStateStore, _Working((trait,))),
        cast(ITraitEvidenceStore, _Evidence({})),
    )
    assert result.selected_tools == ("send_message",)


@pytest.mark.asyncio
async def test_absent_evidence_store_is_a_noop() -> None:
    core = CyberneticCoreState(selected_tools=("send_message",))
    assert await apply_live_grants(
        core, cast(IWorkingStateStore, _Working(())), None
    ) == core
