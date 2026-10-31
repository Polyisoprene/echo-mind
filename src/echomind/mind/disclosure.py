"""Hard gate for private/secret memories: audience admission only, no persona overrides."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Sensitivity = Literal["public", "group", "private", "secret"]


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


def gate(
    *, sensitivity: str, owner_id: str, audience: frozenset[str], venue: str,
    granted: bool = False,
) -> GateDecision:
    """Admit a memory only to an audience that may receive it.

    public/group pass (the persona decides whether to speak); private needs the owner
    present; secret is denied until an explicit grant exists (P4); unknown is denied.
    """
    _ = venue
    if sensitivity in ("public", "group"):
        return GateDecision(True, "public_or_group")
    if not owner_id:
        return GateDecision(False, "unknown_owner")
    if sensitivity == "private":
        return (
            GateDecision(True, "owner_present")
            if owner_id in audience
            else GateDecision(False, "owner_absent")
        )
    if sensitivity == "secret":
        return (
            GateDecision(True, "secret_granted")
            if granted
            else GateDecision(False, "secret_without_grant")
        )
    return GateDecision(False, "unknown_sensitivity")


def gate_fact(
    fact: object, audience: frozenset[str], venue: str, *, granted: bool = False
) -> GateDecision:
    return gate(
        sensitivity=str(getattr(fact, "sensitivity", "")),
        owner_id=str(getattr(fact, "owner_id", "")),
        audience=audience,
        venue=venue,
        granted=granted,
    )


def gate_episode(card: object, audience: frozenset[str], venue: str) -> GateDecision:
    return gate(
        sensitivity=str(getattr(card, "sensitivity", "")),
        owner_id=str(getattr(card, "owner_id", "")),
        audience=audience,
        venue=venue,
    )


__all__ = ["GateDecision", "gate", "gate_episode", "gate_fact"]
