"""Conservative claim supersede planner; shadow only."""

from __future__ import annotations

from collections.abc import Iterable

from echomind.mind.fact_shadow import ClaimView


def plan_supersedes(
    new: ClaimView, existing: Iterable[ClaimView],
) -> tuple[ClaimView, ...]:
    """Only functional value claims with identical privacy/audience context."""
    if new.predicate != "value":
        return ()
    candidates: list[ClaimView] = []
    for old in existing:
        if old.predicate != "value" or old.recorded_at_ms >= new.recorded_at_ms:
            continue
        if (old.chat_key, old.scope, old.owner_id, old.sensitivity) != (
            new.chat_key, new.scope, new.owner_id, new.sensitivity
        ):
            continue
        if old.audience != new.audience:
            continue
        candidates.append(old)
    return tuple(candidates)
