"""Evidence-bound first-person narrative projection; read-only, not in prompt."""

from __future__ import annotations

from dataclasses import dataclass

from echomind.domain.ports import IWorkingStateStore
from echomind.domain.trait_evidence_ports import ITraitEvidenceStore


@dataclass(frozen=True)
class NarrativeIdentity:
    trait_ids: tuple[int, ...]
    lines: tuple[str, ...]


async def build_narrative(
    working: IWorkingStateStore, evidence_store: ITraitEvidenceStore,
) -> NarrativeIdentity:
    traits = tuple(t for t in await working.sync_persona_traits() if t.status == "active")
    lines: list[str] = []
    for trait in traits:
        rows = await evidence_store.list_trait_evidence(trait.trait_id, 1)
        if not rows:
            continue
        lines.append(f"- {trait.trait_text}（有次：{rows[0].quote}）")
    return NarrativeIdentity(tuple(t.trait_id for t in traits), tuple(lines))
