"""Additive live tool grants from active trait evidence; never removes base tools."""

from __future__ import annotations

from echomind.domain.models import (
    CyberneticCoreState,
    Percept,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.domain.ports import IWorkingStateStore
from echomind.domain.trait_evidence_ports import ITraitEvidenceStore
from echomind.mind.cybernetics import compute_cybernetic_core
from echomind.mind.trait_action_eligibility import evaluate_eligibility


async def apply_live_grants(
    core: CyberneticCoreState, working: IWorkingStateStore,
    evidence_store: ITraitEvidenceStore | None,
) -> CyberneticCoreState:
    if evidence_store is None:
        return core
    traits = await working.sync_persona_traits()
    active = tuple(trait for trait in traits if trait.status == "active")
    if not active:
        return core
    rows = {
        trait.trait_id: await evidence_store.list_trait_evidence(trait.trait_id, 50)
        for trait in active
    }
    eligible = evaluate_eligibility(active, rows)
    if not eligible.allowed_tools and not eligible.allow_refusal:
        return core
    tools = tuple(dict.fromkeys((*core.selected_tools, *sorted(eligible.allowed_tools))))
    return core.model_copy(update={
        "selected_tools": tools, "allow_refusal": eligible.allow_refusal,
    })


async def compute_and_grant(
    scene: str, snap: WorkingSnapshot, triggers: tuple[Percept, ...],
    bonds: dict[str, SocialBondProfile], *,
    unknown: tuple[str, ...], warnings: tuple[str, ...],
    chord_reagents: tuple[str, ...], working: IWorkingStateStore,
    evidence_store: ITraitEvidenceStore | None,
) -> CyberneticCoreState:
    core = compute_cybernetic_core(
        scene, snap, triggers, bonds, unknown_terms=unknown,
        warnings=warnings, chord_reagents=chord_reagents,
    )
    return await apply_live_grants(core, working, evidence_store)
