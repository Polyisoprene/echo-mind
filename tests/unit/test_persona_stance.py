"""Stage 30 S30-4: relationship stance shifts rendering, never the stored personality."""

from __future__ import annotations

from echomind.domain.models import PlasticParamSpec, SocialBondProfile
from echomind.domain.persona_specs import PERSONA_SPECS
from echomind.mind.persona_stance import apply_stance_for, stance_for, stance_vector


def _params() -> dict[str, PlasticParamSpec]:
    return {
        key: PlasticParamSpec(key=key, value=spec.default, min_bound=spec.min_bound,
                              max_bound=spec.max_bound, description=spec.description)
        for key, spec in PERSONA_SPECS.items()
    }


DEEP = SocialBondProfile(chat_key="g", user_id="deep", user_name="deep",
                         affinity_score=85.0, trust_score=0.9, bond_depth=90.0)
STRANGER = SocialBondProfile(chat_key="g", user_id="cold", user_name="cold",
                             affinity_score=20.0, trust_score=0.5, bond_depth=0.0)


def test_deep_and_stranger_get_different_warmth() -> None:
    deep = apply_stance_for(_params(), {"deep": DEEP}, "deep")["persona_warmth"].value
    cold = apply_stance_for(_params(), {"cold": STRANGER}, "cold")["persona_warmth"].value
    assert deep - cold >= 0.15, f"stance too weak: deep={deep} cold={cold}"


def test_stored_personality_is_not_mutated() -> None:
    params = _params()
    shifted = apply_stance_for(params, {"deep": DEEP}, "deep")
    assert params["persona_warmth"].value == PERSONA_SPECS["persona_warmth"].default
    assert shifted is not params


def test_unknown_sender_keeps_identity_stance() -> None:
    assert stance_for({}, "ghost") == (0.0, 0.0, 0.0)


def test_stance_is_bounded() -> None:
    for bond in (DEEP, STRANGER):
        sigma = stance_vector(bond)
        assert all(-1.0 <= s <= 1.0 for s in sigma)
