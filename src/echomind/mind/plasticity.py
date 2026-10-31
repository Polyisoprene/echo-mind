"""M3.4/M26.2 Neuroplasticity & Dynamic Personality Self-Learning Engine (Zero Lexicons).

Personality is two layers:
  * trait baseline (`plastic_params`) — settled once per day by at most TRAIT_DAILY_PUSH;
  * fast state (`persona_state`) — reacts to every turn, bounded and decaying.
A turn therefore never rewrites the baseline; it only records state + evidence.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from echomind.domain.models import PlasticParamSpec, TurnOutcome
from echomind.domain.persona_specs import PERSONA_SPECS
from echomind.domain.ports import IPersonaLayerStore, IWorkingStateStore
from echomind.domain.trait_evidence import TraitEvidence
from echomind.domain.trait_evidence_ports import ITraitEvidenceStore
from echomind.mind.persona_dynamics import TRAIT_DAILY_PUSH, slow_regression
from echomind.mind.persona_state import step_state
from echomind.mind.personality import compute_personality_deltas, derive_emergent_trait
from echomind.mind.subconscious_probe import compute_chord_social_reward
from echomind.mind.trait_evidence_writer import evidence_context, trait_quote

if TYPE_CHECKING:
    from echomind.mind.subconscious_probe import SubconsciousChordResult

DAY_MS = 86_400_000.0

PARAM_BASELINES: dict[str, float] = {
    "talkativeness": 58.0,
    "proactive_idle_min": 10.0,
    "skepticism": 55.0,
    "verify_impulse": 70.0,
    "curiosity_rate": 65.0,
    **{key: spec.default for key, spec in PERSONA_SPECS.items()},
}
HOMEOSTATIC_PULL_RATE = 0.02


def boundary_damping(value: float, delta: float, lo: float, hi: float) -> float:
    """Shrink same-direction gain as a parameter approaches its homeostatic bound."""
    if delta == 0.0 or hi <= lo:
        return delta
    headroom = (hi - value) / (hi - lo) if delta > 0 else (value - lo) / (hi - lo)
    return delta * max(0.0, min(1.0, headroom * 2.0))


def trait_strength_shift(reward: float) -> tuple[int, tuple[str, ...]]:
    """Map reward polarity to (direction, affected categories).

    Negative experiences only erode taboos/temperament; positive ones only reinforce
    habits/tastes — one bad turn must not weaken unrelated habits.
    """
    if reward >= 0.5:
        return 1, ()
    if reward <= -0.5:
        return -1, ("taboo", "temperament")
    return 0, ()


def homeostatic_pull(key: str, current: float) -> float:
    """Pull a drifted behavioral parameter gently back toward its baseline."""
    baseline = PARAM_BASELINES.get(key)
    if baseline is None:
        return 0.0
    return round((baseline - current) * HOMEOSTATIC_PULL_RATE, 3)


def compute_param_deltas(outcome: TurnOutcome) -> list[tuple[str, float, str]]:
    """Compute bounded behavioral & 7D personality observations from one turn."""
    adjustments: list[tuple[str, float, str]] = []
    reward = outcome.social_reward

    if outcome.epistemic_conflict_detected:
        adjustments.append(("skepticism", 5.0, "检测到群友身份忽悠/事实冲突，自主上调防忽悠警觉度"))
        adjustments.append(
            ("verify_impulse", 4.0, "吃一堑长一智，上调遇到可疑说法主动调工具核验冲动")
        )

    if reward >= 0.45:
        adjustments.append(
            (
                "talkativeness",
                round(reward * 2.2, 2),
                "发言获得群友积极接茬互动，上调群聊插话积极度",
            )
        )
        adjustments.append(
            ("proactive_idle_min", -0.5, "互动气氛热烈，略微缩短冷场主动等待时间")
        )
    elif reward <= -0.3:
        adjustments.append(
            ("talkativeness", round(reward * 4.0, 2), "发言后冷场或受挫，自主收敛群聊插话积极度")
        )
        adjustments.append(
            ("proactive_idle_min", 1.0, "避免刷屏打扰，自主延长冷场主动开口等待时间")
        )

    if any(t in ("web_search", "meme_wiki", "web_fetch", "read_video") for t in outcome.tools_used):
        adjustments.append(("curiosity_rate", 2.0, "主动使用搜索/梗百科工具探索未知，强化求知欲"))

    adjustments.extend(compute_personality_deltas(outcome))
    return adjustments


def _bounded(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


class NeuroplasticityEngine:
    """Apply behavioral reinforcement and two-layer persona learning."""

    def __init__(
        self, store: IWorkingStateStore, layers: IPersonaLayerStore | None = None,
        *, evidence_store: ITraitEvidenceStore | None = None,
    ) -> None:
        self._store = store
        self._layers = layers
        self._evidence = evidence_store

    async def _observe_param(self, key: str, delta: float, now_ms: int) -> None:
        """Move the fast state and buffer the observation for the next settlement.

        Used for every plastic parameter when the layer store is wired: the baseline
        never moves on a turn, so the two-layer contract is uniform across persona
        and behaviour parameters.
        """
        if self._layers is None:
            return
        offset, _ = step_state(await self._layers.load_state(), key, delta, now_ms)
        await self._layers.save_state(key, offset, now_ms)
        await self._layers.record_observation(key, delta, now_ms)

    async def adapt_from_outcome(self, outcome: TurnOutcome) -> tuple[PlasticParamSpec, ...]:
        deltas = compute_param_deltas(outcome)
        if not deltas:
            return ()
        now_ms = int(time.time() * 1000)
        current = await self._store.get_plastic_params()
        updated: list[PlasticParamSpec] = []
        for key, delta, reason in deltas:
            if self._layers is not None:
                await self._observe_param(key, delta, now_ms)
                continue
            if key.startswith("persona_"):
                continue
            applied = await self._apply_one(key, delta, reason, current, outcome.social_reward)
            if applied is not None:
                updated.append(applied)
        await self._learn_traits(outcome)
        return tuple(updated)

    async def _learn_traits(self, outcome: TurnOutcome) -> None:
        emergent = derive_emergent_trait(outcome)
        shift, decay_cats = trait_strength_shift(outcome.social_reward)
        if emergent is None and shift == 0:
            return
        traits = await self._store.sync_persona_traits(
            new_trait=emergent, strength_delta=shift, chat_key=outcome.chat_key,
            source=f"turn:{outcome.session_id}", decay_categories=decay_cats,
        )
        if emergent is None:
            return
        quote = trait_quote(outcome)
        match = next(
            (trait for trait in traits if trait.trait_text == emergent.trait_text.strip()),
            None,
        )
        if quote is None or match is None or self._evidence is None:
            return
        now_ms = int(time.time() * 1000)
        quote_kind, quote_text = quote
        await self._evidence.record_trait_evidence(TraitEvidence(
            trait_id=match.trait_id, session_id=outcome.session_id,
            turn_id=outcome.session_id, quote=quote_text, quote_kind=quote_kind,
            polarity=1, context_hash=evidence_context(outcome, now_ms),
            created_ms=now_ms,
        ))

    async def _apply_one(
        self, key: str, delta: float, reason: str,
        current: dict[str, PlasticParamSpec], reward: float,
    ) -> PlasticParamSpec | None:
        """Damp, homeostatically pull and persist one behavioral parameter."""
        snap = current.get(key)
        if snap is None:
            return None
        damped = boundary_damping(snap.value, delta, snap.min_bound, snap.max_bound)
        total = round(damped + homeostatic_pull(key, snap.value), 3)
        clamped = max(snap.min_bound, min(snap.max_bound, round(snap.value + total, 3)))
        if abs(clamped - snap.value) < 0.005:
            return None
        return await self._store.update_plastic_param(
            key=key, delta=total, reason=reason, reward=reward
        )

    async def settle_baseline(self, now_ms: int) -> tuple[PlasticParamSpec, ...]:
        """Apply one day of buffered evidence to the slow baseline, bounded and slow."""
        if self._layers is None:
            return ()
        buckets = await self._layers.pop_observations(now_ms)
        if not buckets:
            return ()
        params = await self._store.get_plastic_params()
        updated: list[PlasticParamSpec] = []
        for key, (total, last_ms) in buckets.items():
            applied = await self._settle_one(key, total, last_ms, params, now_ms)
            if applied is not None:
                updated.append(applied)
        return tuple(updated)

    async def _settle_one(
        self,
        key: str,
        total: float,
        last_ms: int,
        params: dict[str, PlasticParamSpec],
        now_ms: int,
    ) -> PlasticParamSpec | None:
        snap = params.get(key)
        if snap is None:
            return None
        days = max(0.0, (now_ms - last_ms) / DAY_MS) if last_ms else 1.0
        baseline = PARAM_BASELINES.get(key, snap.value)
        regression = slow_regression(snap.value, baseline, days)
        wanted = _bounded(_bounded(total, TRAIT_DAILY_PUSH) + regression, TRAIT_DAILY_PUSH)
        target = max(snap.min_bound, min(snap.max_bound, snap.value + wanted))
        delta = round(target - snap.value, 4)
        if abs(delta) < 1e-4:
            return None
        return await self._store.update_plastic_param(
            key=key, delta=delta, reason="日结算：特质基线缓慢漂移", reward=0.0
        )

    async def adapt_from_exogenous_info(
        self, kind: str, topic: str
    ) -> tuple[PlasticParamSpec, ...]:
        """Surfing may raise curiosity, but must not move the slow personality baseline."""
        if self._layers is not None:
            await self._observe_param("curiosity_rate", 0.6, int(time.time() * 1000))
            return ()
        current = await self._store.get_plastic_params()
        label = topic[:18] or kind
        snap = current.get("curiosity_rate")
        if snap is None:
            return ()
        damped = boundary_damping(snap.value, 0.6, snap.min_bound, snap.max_bound)
        total = round(damped + homeostatic_pull("curiosity_rate", snap.value), 3)
        if abs(total) < 0.005:
            return ()
        applied = await self._store.update_plastic_param(
            key="curiosity_rate", delta=total,
            reason=f"自主冲浪探索({label})，对外部世界求知欲强化", reward=0.35,
        )
        return (applied,)


def apply_chord_reward(
    outcome: TurnOutcome,
    cache: dict[str, SubconsciousChordResult],
) -> tuple[TurnOutcome, SubconsciousChordResult | None]:
    """Re-derive social_reward from the cached 6D chord so learning reflects real semantics."""
    if not outcome.triggers:
        return outcome, None
    chord = cache.get(outcome.triggers[-1].message_id)
    if chord is None:
        return outcome, None
    is_poke = any(p.is_poke_me for p in outcome.triggers)
    reward = compute_chord_social_reward(chord, is_poke=is_poke)
    return outcome.model_copy(update={"social_reward": reward}), chord


def compute_turn_social_reward(
    text: str = "",
    *,
    is_poke: bool = False,
    is_owner: bool = False,
    chord: SubconsciousChordResult | None = None,
) -> float:
    """Compute social reinforcement reward [-0.85, +0.85] from 6D Subconscious Chord."""
    _ = text
    return compute_chord_social_reward(chord, is_poke=is_poke, is_owner=is_owner)
