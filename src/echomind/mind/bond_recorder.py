"""Record per-turn bond-depth observations (impact / betrayal) for the people involved."""

from __future__ import annotations

from echomind.domain.models import TurnOutcome
from echomind.domain.ports import IBondDepthStore


async def record_turn_events(store: IBondDepthStore | None, outcome: TurnOutcome) -> None:
    """Write one impact observation per distinct trigger sender (betrayal = verified deception)."""
    if store is None or not outcome.triggers:
        return
    magnitude = abs(outcome.social_reward)
    seen: set[str] = set()
    for percept in outcome.triggers:
        uid = percept.sender_id
        if not uid or uid in seen:
            continue
        seen.add(uid)
        await store.add_impact(
            outcome.chat_key, uid, magnitude, betray=outcome.epistemic_conflict_detected
        )
