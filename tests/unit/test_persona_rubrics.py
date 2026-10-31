"""A3-b: every tier carries a behavioural tone reference; guile covers both branches."""

from __future__ import annotations

from echomind.domain.models import PlasticParamSpec
from echomind.domain.persona_specs import PERSONA_SPECS
from echomind.mind.persona_rubrics import DIMENSION_RUBRICS
from echomind.mind.personality import synthesize_live_persona_directive


def _params() -> dict[str, PlasticParamSpec]:
    return {
        key: PlasticParamSpec(
            key=key,
            value=spec.default,
            min_bound=spec.min_bound,
            max_bound=spec.max_bound,
            description=spec.description,
        )
        for key, spec in PERSONA_SPECS.items()
    }


def test_each_tier_has_a_tone_reference() -> None:
    for spec in DIMENSION_RUBRICS:
        for text in spec[6:9]:
            assert "语气参考" in text or "例：" in text, spec[0]


def test_guile_covers_both_branches() -> None:
    guile = next(spec for spec in DIMENSION_RUBRICS if spec[0] == "persona_guile")
    assert "开脱" in guile[6], "self-serving excuse branch is missing"
    assert "圆场" in guile[6], "covering for a friend branch is missing"


def test_directive_forbids_copying_examples() -> None:
    text = synthesize_live_persona_directive(_params(), ())
    assert "不要照抄" in text
