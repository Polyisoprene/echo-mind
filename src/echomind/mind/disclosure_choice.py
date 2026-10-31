"""Persona-driven choice among the actions the hard gate already allowed."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Action = Literal["say", "hint", "keep"]


@dataclass(frozen=True)
class DisclosureChoice:
    action: Action
    reason: str


def choose(
    *,
    sensitivity: str,
    has_owner: bool,
    rival_present: bool,
    traits: Mapping[str, float],
    granted: bool = False,
) -> DisclosureChoice:
    """A transparent rule set over the 7D scale; thresholds are conventions on 0-100.

    defaults (55/62/52/75/48) -> say; high guile/tsundere -> hint;
    high possessiveness with a rival around -> keep; high defiance -> say.
    """
    if sensitivity == "secret" and not granted:
        return DisclosureChoice("keep", "secret")
    if sensitivity == "private" and not has_owner:
        return DisclosureChoice("keep", "unknown_owner")
    if rival_present and traits.get("persona_possessiveness", 0.0) >= 80.0:
        return DisclosureChoice("keep", "possessive_rival")
    if traits.get("persona_defiance", 0.0) >= 65.0:
        return DisclosureChoice("say", "defiant")
    if traits.get("persona_guile", 0.0) >= 60.0 or traits.get("persona_tsundere", 0.0) >= 65.0:
        return DisclosureChoice("hint", "indirect")
    return DisclosureChoice("say", "direct")


__all__ = ["DisclosureChoice", "choose"]
