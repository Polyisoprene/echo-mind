"""P0.3: warmth/patience follow the person; play follows the venue."""

from __future__ import annotations

from echomind.domain.models import PlasticParamSpec, SocialBondProfile
from echomind.mind.person_level import PersonProfile
from echomind.mind.persona_stance import apply_stance_for


def _params() -> dict[str, PlasticParamSpec]:
    specs = (
        ("persona_warmth", 65.0, 15.0, 98.0),
        ("persona_tsundere", 62.0, 10.0, 95.0),
        ("persona_playfulness", 58.0, 15.0, 95.0),
        ("persona_defiance", 48.0, 10.0, 95.0),
        ("persona_confidence", 55.0, 15.0, 95.0),
    )
    return {
        key: PlasticParamSpec(key=key, value=value, min_bound=low, max_bound=high)
        for key, value, low, high in specs
    }


def test_same_person_keeps_warmth_and_changes_play() -> None:
    profile = PersonProfile(
        "u", trust=0.663, affinity=47.45, depth_raw=92.5, depth_percentile=100.0
    )
    group = SocialBondProfile(chat_key="g", user_id="u", user_name="u",
                              affinity_score=54.5, trust_score=0.61, msg_count=680)
    private = SocialBondProfile(chat_key="p", user_id="u", user_name="u",
                                affinity_score=32.1, trust_score=0.78, msg_count=312)
    params = _params()

    in_group = apply_stance_for(params, {"u": group}, "u", {"u": profile})
    in_private = apply_stance_for(params, {"u": private}, "u", {"u": profile})

    assert in_group["persona_warmth"].value == in_private["persona_warmth"].value
    assert in_group["persona_defiance"].value == in_private["persona_defiance"].value
    assert in_group["persona_playfulness"].value > in_private["persona_playfulness"].value
