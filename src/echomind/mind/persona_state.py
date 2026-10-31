"""Two-layer persona: a slow trait baseline plus fast, decaying state offsets.

The baseline lives in `plastic_params` and moves at most once per day by
`TRAIT_DAILY_PUSH`. The state layer lives in `persona_state`, reacts to every turn,
is bounded by `STATE_MAX_ABS` and decays with a `STATE_HALF_LIFE_MIN` half-life.
What the model sees is `baseline + decayed(state)`, clamped to the declared bounds.
"""

from __future__ import annotations

from echomind.domain.models import PlasticParamSpec
from echomind.domain.ports import IPersonaLayerStore, IWorkingStateStore
from echomind.mind.persona_dynamics import (
    STATE_HALF_LIFE_MIN,
    STATE_MAX_ABS,
    STATE_MAX_STEP,
)

StateMap = dict[str, tuple[float, int]]


def decay_offset(offset: float, elapsed_ms: float) -> float:
    """Exponential decay of a state offset with the configured half-life."""
    if offset == 0.0 or elapsed_ms <= 0.0:
        return offset
    half_life_ms = STATE_HALF_LIFE_MIN * 60_000.0
    return float(offset * (0.5 ** (elapsed_ms / half_life_ms)))


def step_state(
    state: StateMap, key: str, delta: float, now_ms: int
) -> tuple[float, int]:
    """Apply one bounded observation to a key and return its (offset, updated_ms)."""
    previous, updated_ms = state.get(key, (0.0, now_ms))
    carried = decay_offset(previous, float(now_ms - updated_ms))
    step = max(-STATE_MAX_STEP, min(STATE_MAX_STEP, delta))
    value = max(-STATE_MAX_ABS, min(STATE_MAX_ABS, carried + step))
    return round(value, 3), now_ms


def effective_params(
    params: dict[str, PlasticParamSpec], state: StateMap, now_ms: int
) -> dict[str, PlasticParamSpec]:
    """Overlay decayed state offsets on the baseline and clamp to declared bounds."""
    merged: dict[str, PlasticParamSpec] = {}
    for key, spec in params.items():
        offset, updated_ms = state.get(key, (0.0, now_ms))
        raw = spec.value + decay_offset(offset, float(now_ms - updated_ms))
        value = round(max(spec.min_bound, min(spec.max_bound, raw)), 2)
        merged[key] = spec.model_copy(update={"value": value})
    return merged


async def effective_params_of(
    working: IWorkingStateStore,
    layers: IPersonaLayerStore | None,
    now_ms: int,
) -> dict[str, PlasticParamSpec]:
    """Baseline plus state; degrades to the baseline when no layer store is wired."""
    params = await working.get_plastic_params()
    if layers is None:
        return params
    return effective_params(params, await layers.load_state(), now_ms)
