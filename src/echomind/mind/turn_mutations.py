"""Pure mutators for one turn's working-state changes (D16)."""

from __future__ import annotations

from echomind.domain.models import WorkingSnapshot
from echomind.mind.salience_hydraulics import apply_speaking_satiation
from echomind.mind.shadow_appraisal import filter_unfulfilled_intentions


def with_irritation_delta(snapshot: WorkingSnapshot, delta: float) -> WorkingSnapshot:
    value = max(0.0, min(100.0, round(snapshot.affect.irritation + delta, 2)))
    return snapshot.model_copy(update={"affect": snapshot.affect.model_copy(
        update={"irritation": value})})


def satiate_snapshot(
    snapshot: WorkingSnapshot, sent_texts: tuple[str, ...],
    tools_used: tuple[str, ...], now_ms: int,
) -> WorkingSnapshot:
    remaining = filter_unfulfilled_intentions(snapshot.intentions, sent_texts, now_ms)
    return apply_speaking_satiation(
        snapshot.model_copy(update={"intentions": remaining}), sent_texts, tools_used,
    )


__all__ = ["satiate_snapshot", "with_irritation_delta"]
