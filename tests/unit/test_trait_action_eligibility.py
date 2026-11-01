"""P4: eligibility is permission-only, not a score."""

from __future__ import annotations

from echomind.domain.models import PersonaTrait
from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.trait_action_eligibility import Eligibility, evaluate_eligibility


def _trait(trait_id: int, category: str, text: str = "t") -> PersonaTrait:
    return PersonaTrait(trait_id=trait_id, category=category, trait_text=text)  # type: ignore[arg-type]


def _evidence(trait_id: int, quote: str, kind: str, eid: int) -> TraitEvidence:
    return TraitEvidence(
        evidence_id=eid, trait_id=trait_id, session_id="s", turn_id="t",
        quote=quote, quote_kind=kind, polarity=1,  # type: ignore[arg-type]
        context_hash=f"c{eid}", created_ms=eid,
    )


def test_taboo_allows_refusal_only() -> None:
    result = evaluate_eligibility((_trait(1, "taboo"),), {})
    assert result.allow_refusal is True
    assert result.allowed_tools == frozenset()


def test_habit_allows_only_tools_in_evidence() -> None:
    evidence = {
        1: (
            _evidence(1, "look_at_image", "tool", 1),
            _evidence(1, "这句话不是工具", "assistant", 2),
        )
    }
    result = evaluate_eligibility((_trait(1, "habit"),), evidence)
    assert result.allowed_tools == frozenset({"look_at_image"})
    assert result.allow_refusal is False


def test_empty_traits_allow_nothing() -> None:
    result = evaluate_eligibility((), {})
    assert result.allowed_tools == frozenset() and result.allow_refusal is False


def test_empty_grants_do_not_restrict_tools() -> None:
    eligible = Eligibility()
    assert eligible.permits_tool("send_message")
    assert eligible.permits_tool("look_at_image")


def test_nonempty_grants_are_a_whitelist() -> None:
    eligible = Eligibility(allowed_tools=frozenset({"look_at_image"}))
    assert eligible.permits_tool("look_at_image")
    assert not eligible.permits_tool("send_message")
