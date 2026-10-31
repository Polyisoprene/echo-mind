"""Render old vs promoted-candidate persona directives without changing live."""

from __future__ import annotations

from dataclasses import dataclass

from echomind.domain.models import PersonaTrait, PlasticParamSpec
from echomind.domain.trait_candidate import TraitCandidate
from echomind.mind.personality import synthesize_live_persona_directive


@dataclass(frozen=True)
class PromptShadow:
    old: str
    new: str

    @property
    def old_len(self) -> int:
        return len(self.old)

    @property
    def new_len(self) -> int:
        return len(self.new)

    @property
    def len_delta(self) -> int:
        return self.new_len - self.old_len


def build_shadow_prompts(
    params: dict[str, PlasticParamSpec], traits: tuple[PersonaTrait, ...],
    candidate: TraitCandidate,
) -> PromptShadow:
    """Replace one trait's text with the candidate; keep every other input fixed."""
    old = synthesize_live_persona_directive(params, traits)
    replaced = tuple(
        PersonaTrait(
            trait_id=trait.trait_id, category=candidate.category,
            trait_text=candidate.trait_text, strength=trait.strength,
            evidence_count=trait.evidence_count,
            contradiction_count=trait.contradiction_count,
        ) if trait.trait_id == candidate.trait_id else trait
        for trait in traits
    )
    new = synthesize_live_persona_directive(params, replaced)
    return PromptShadow(old=old, new=new)
