"""Conservative sensitivity cues: strong secret phrases, then private phrases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from echomind.domain.models import EpisodicCard, SemanticFact

Sensitivity = Literal["group", "private", "secret"]

SECRET_CUES = (
    "别告诉别人", "不要告诉别人", "别跟别人说", "别到处说", "这是秘密", "保密",
    "只告诉你一个人", "别说出去", "别外传", "就你知道",
)
PRIVATE_CUES = (
    "私聊", "悄悄告诉你", "只和你说", "别在群里说", "别让别人知道",
)


@dataclass(frozen=True)
class SensitivityVerdict:
    sensitivity: Sensitivity
    confidence: float
    evidence: str


def classify(text: str) -> SensitivityVerdict:
    """Return the strongest cue found; default is group with no evidence."""
    for cue in SECRET_CUES:
        if cue in text:
            return SensitivityVerdict("secret", 0.9, cue)
    for cue in PRIVATE_CUES:
        if cue in text:
            return SensitivityVerdict("private", 0.75, cue)
    return SensitivityVerdict("group", 1.0, "")


__all__ = ["SensitivityVerdict", "classify", "upgrade_episode", "upgrade_fact"]


def upgrade_fact(fact: SemanticFact) -> SemanticFact:
    if fact.sensitivity != "group":
        return fact
    verdict = classify(f"{fact.fact_text} {fact.source_quote}")
    if verdict.sensitivity == "group":
        return fact
    return fact.model_copy(update={
        "sensitivity": verdict.sensitivity,
        "owner_id": fact.owner_id or fact.source_person_id,
    })


def upgrade_episode(card: EpisodicCard) -> EpisodicCard:
    if card.sensitivity != "group":
        return card
    verdict = classify(f"{card.summary} {card.key_detail} {card.source_quote}")
    if verdict.sensitivity == "group":
        return card
    return card.model_copy(update={
        "sensitivity": verdict.sensitivity,
        "owner_id": card.owner_id or card.source_person_id,
    })
