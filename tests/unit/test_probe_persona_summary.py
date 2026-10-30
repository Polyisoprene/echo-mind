"""Stage 30 S30-6: the probe sees a one-line personality digest; renders are cached."""

from __future__ import annotations

from echomind.domain.models import PlasticParamSpec
from echomind.domain.persona_specs import PERSONA_SPECS
from echomind.mind.persona_render import cache_hits, persona_summary
from echomind.mind.personality import synthesize_live_persona_directive
from echomind.mind.subconscious_probe import build_probe_system_prompt


def _params(possess: float = 93.0) -> dict[str, PlasticParamSpec]:
    return {
        key: PlasticParamSpec(
            key=key, value=(possess if key == "persona_possessiveness" else spec.default),
            min_bound=spec.min_bound, max_bound=spec.max_bound, description=spec.description,
        )
        for key, spec in PERSONA_SPECS.items()
    }


def test_probe_prompt_contains_persona_digest() -> None:
    synthesize_live_persona_directive(_params(93.0), ())
    prompt = build_probe_system_prompt()
    assert "当前人格基调" in prompt
    assert "独占93" in prompt
    assert persona_summary() in prompt


def test_directive_render_is_cached() -> None:
    params = _params(80.0)
    synthesize_live_persona_directive(params, ())
    before = cache_hits()
    synthesize_live_persona_directive(params, ())
    assert cache_hits() == before + 1
