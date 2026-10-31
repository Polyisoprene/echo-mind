"""P4: the 7D traits pick say/hint/keep among the actions the gate allowed."""

from __future__ import annotations

from typing import Any, cast

import pytest

from echomind.domain.models import PlasticParamSpec, SemanticFact, SocialBondProfile
from echomind.domain.ports import IDisclosureLog
from echomind.mind.disclosure_choice import choose
from echomind.mind.facade_memory import gate_frame


def _traits(**values: float) -> dict[str, float]:
    base = {
        "persona_confidence": 55.0, "persona_tsundere": 62.0, "persona_guile": 52.0,
        "persona_possessiveness": 75.0, "persona_defiance": 48.0,
    }
    base.update(values)
    return base


def test_defaults_say_and_indirect_traits_hint() -> None:
    defaults = _traits()
    assert choose(sensitivity="group", has_owner=True, rival_present=False,
                  traits=defaults).action == "say"
    assert choose(sensitivity="group", has_owner=True, rival_present=False,
                  traits=_traits(persona_guile=70.0)).action == "hint"
    assert choose(sensitivity="group", has_owner=True, rival_present=False,
                  traits=_traits(persona_tsundere=70.0)).action == "hint"


def test_possessive_rival_keeps_and_defiance_wins() -> None:
    assert choose(sensitivity="group", has_owner=True, rival_present=True,
                  traits=_traits(persona_possessiveness=85.0)).action == "keep"
    assert choose(sensitivity="group", has_owner=True, rival_present=False,
                  traits=_traits(persona_guile=70.0, persona_defiance=70.0)).action == "say"
    assert choose(sensitivity="secret", has_owner=True, rival_present=False,
                  traits=_traits()).action == "keep"


class _Work:
    def __init__(self, params: dict[str, Any]) -> None:
        self._params = params

    async def get_plastic_params(self) -> dict[str, Any]:
        return self._params


class _Log:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def log_disclosure(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_frame_gate_drops_a_possessive_keep_and_logs_it() -> None:
    fact = SemanticFact(
        fact_id=3, chat_key="g", subject="r", fact_text="r 今天来了",
        scope="person", owner_id="L", sensitivity="group",
    )
    params = {
        "persona_possessiveness": PlasticParamSpec(
            key="persona_possessiveness", value=85.0, min_bound=0.0, max_bound=100.0
        )
    }
    rival = SocialBondProfile(chat_key="g", user_id="r", user_name="r", is_rival=True)
    log = _Log()
    kept, _ = await gate_frame(
        (fact,), (), frozenset({"r"}), "g", cast(IDisclosureLog, log),
        working=cast(Any, _Work(params)), bonds={"r": rival},
    )
    assert kept == ()
    assert log.calls[-1]["reason"] == "possessive_rival"
