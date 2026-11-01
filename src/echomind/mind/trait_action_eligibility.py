"""P4: derive action eligibility from active traits and their evidence.

Eligibility is a set of permissions, never a score. A tool is allowed only when
the active trait's evidence explicitly records that tool; a taboo trait allows
refusal. This is intentionally conservative and shadow-only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from echomind.domain.models import PersonaTrait
from echomind.domain.trait_evidence import TraitEvidence


@dataclass(frozen=True)
class Eligibility:
    allowed_tools: frozenset[str] = frozenset()
    allow_refusal: bool = False
    reasons: tuple[str, ...] = ()

    def permits_tool(self, tool: str) -> bool:
        """Empty grants mean "no restriction"; a non-empty set is a whitelist."""
        return not self.allowed_tools or tool in self.allowed_tools


def _tools(rows: tuple[TraitEvidence, ...]) -> set[str]:
    return {row.quote for row in rows if row.quote_kind == "tool"}


def evaluate_eligibility(
    traits: tuple[PersonaTrait, ...],
    evidence: Mapping[int, tuple[TraitEvidence, ...]],
) -> Eligibility:
    tools: set[str] = set()
    allow_refusal = False
    reasons: list[str] = []
    for trait in traits:
        rows = evidence.get(trait.trait_id, ())
        trait_tools = _tools(rows)
        tools.update(trait_tools)
        reasons.extend(f"{trait.trait_id}:tool→{tool}" for tool in trait_tools)
        if trait.category == "taboo":
            allow_refusal = True
            reasons.append(f"{trait.trait_id}:taboo→refusal")
    return Eligibility(frozenset(tools), allow_refusal, tuple(reasons))
