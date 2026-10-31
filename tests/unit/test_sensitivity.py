"""P3.3: strong cues upgrade a group memory to private/secret."""

from __future__ import annotations

from echomind.domain.models import SemanticFact
from echomind.mind.sensitivity import classify, upgrade_fact


def test_classify_cues() -> None:
    assert classify("别告诉别人我在医院").sensitivity == "secret"
    assert classify("悄悄告诉你一件事").sensitivity == "private"
    assert classify("今天天气不错").sensitivity == "group"


def test_upgrade_fact_sets_owner_and_never_downgrades() -> None:
    fact = SemanticFact(
        chat_key="group:1", subject="病", fact_text="别告诉别人，我在休养",
        source_person_id="L",
    )
    upgraded = upgrade_fact(fact)
    assert upgraded.sensitivity == "secret"
    assert upgraded.owner_id == "L"
    assert upgrade_fact(upgraded) == upgraded
