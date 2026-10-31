"""Autonomous-tick helpers kept out of the facade's line budget."""

from __future__ import annotations

from echomind.domain.models import ProactiveProposal, WorkingSnapshot
from echomind.domain.ports import IWorkingStateStore
from echomind.mind.cybernetics import consume_proposal_snapshot
from echomind.mind.drives_temporal import apply_temporal_decay_and_circadian
from echomind.mind.explorer import arbitrate_autonomous_action
from echomind.mind.plasticity import NeuroplasticityEngine
from echomind.mind.working_update import mutate_working_state


async def run_autonomous_tick(
    working: IWorkingStateStore,
    plasticity: NeuroplasticityEngine,
    last_active_ms: int,
    operator_ids: tuple[str, ...],
    default_group: str,
    *,
    now_ms: int,
) -> tuple[ProactiveProposal | None, int]:
    """Settle the baseline, then arbitrate one autonomous action on the latest snapshot."""
    await plasticity.settle_baseline(now_ms)
    params = await working.get_plastic_params()
    idle_target = params["proactive_idle_min"].value if "proactive_idle_min" in params else 10.0
    proposals: list[ProactiveProposal] = []

    def mutate(snap: WorkingSnapshot) -> WorkingSnapshot:
        idle_min = max(0.0, (now_ms - last_active_ms) / 60_000.0)
        priv_key = f"private:{operator_ids[0]}" if operator_ids else ""
        proposal = arbitrate_autonomous_action(
            snap, default_group, priv_key, idle_min,
            proactive_idle_min=idle_target, now_ms=now_ms,
        )
        if proposal is not None:
            proposals.append(proposal)
            return consume_proposal_snapshot(snap, proposal)
        return apply_temporal_decay_and_circadian(snap, min(idle_min, 30.0), now_ms)

    await mutate_working_state(working, "global", mutate)
    if proposals:
        return proposals[0], max(last_active_ms, now_ms)
    return None, last_active_ms

__all__ = ["run_autonomous_tick"]
