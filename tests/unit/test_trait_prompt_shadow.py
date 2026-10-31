"""Promoted-candidate prompt shadow changes only the trait line."""

from __future__ import annotations

from echomind.domain.models import PersonaTrait, PlasticParamSpec
from echomind.domain.trait_candidate import TraitCandidate
from echomind.mind.plasticity import PARAM_BASELINES
from echomind.mind.trait_prompt_shadow import build_shadow_prompts


def _params() -> dict[str, PlasticParamSpec]:
    return {
        key: PlasticParamSpec(key=key, value=value, min_bound=0, max_bound=100)
        for key, value in PARAM_BASELINES.items()
    }


def test_candidate_replaces_only_the_trait_text() -> None:
    trait = PersonaTrait(trait_id=7, category="habit", trait_text="旧习惯", strength=6)
    candidate = TraitCandidate(
        trait_id=7, category="habit", trait_text="看到图会先找小槽点",
        evidence_json="[]", prompt_hash="h", status="promoted", created_ms=1,
    )
    shadow = build_shadow_prompts(_params(), (trait,), candidate)
    assert "旧习惯" in shadow.old
    assert "看到图会先找小槽点" not in shadow.old
    assert "看到图会先找小槽点" in shadow.new
    assert shadow.len_delta == len(shadow.new) - len(shadow.old)
