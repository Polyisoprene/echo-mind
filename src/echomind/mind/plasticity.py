"""M3.4/M26.2 Neuroplasticity & Dynamic Personality Self-Learning Engine (Zero Lexicons)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from echomind.domain.models import PlasticParamSpec, TurnOutcome
from echomind.domain.ports import IWorkingStateStore
from echomind.mind.personality import compute_personality_deltas, derive_emergent_trait
from echomind.mind.subconscious_probe import compute_chord_social_reward

if TYPE_CHECKING:
    from echomind.mind.subconscious_probe import SubconsciousChordResult

PARAM_BASELINES: dict[str, float] = {
    "talkativeness": 58.0,
    "proactive_idle_min": 10.0,
    "skepticism": 55.0,
    "verify_impulse": 70.0,
    "curiosity_rate": 65.0,
    "persona_warmth": 65.0,
    "persona_tsundere": 62.0,
    "persona_playfulness": 58.0,
    "persona_possessiveness": 75.0,
    "persona_confidence": 55.0,
    "persona_guile": 52.0,
    "persona_defiance": 48.0,
}
HOMEOSTATIC_PULL_RATE = 0.02


def boundary_damping(value: float, delta: float, lo: float, hi: float) -> float:
    """Shrink same-direction gain as a parameter approaches its homeostatic bound."""
    if delta == 0.0 or hi <= lo:
        return delta
    headroom = (hi - value) / (hi - lo) if delta > 0 else (value - lo) / (hi - lo)
    return delta * max(0.0, min(1.0, headroom * 2.0))


def trait_strength_shift(reward: float) -> int:
    """Map social reward polarity to persona-trait reinforcement direction."""
    if reward >= 0.5:
        return 1
    if reward <= -0.5:
        return -1
    return 0


def homeostatic_pull(key: str, current: float) -> float:
    """Pull a drifted parameter gently back toward its evolutionary baseline."""
    baseline = PARAM_BASELINES.get(key)
    if baseline is None:
        return 0.0
    return round((baseline - current) * HOMEOSTATIC_PULL_RATE, 3)


def compute_param_deltas(outcome: TurnOutcome) -> list[tuple[str, float, str]]:
    """Compute bounded behavioral & 5D personality deltas from turn outcome."""
    adjustments: list[tuple[str, float, str]] = []
    reward = outcome.social_reward

    # 1. Epistemic prediction error (was fooled or spoofed by a group member)
    if outcome.epistemic_conflict_detected:
        adjustments.append(("skepticism", 5.0, "检测到群友身份忽悠/事实冲突，自主上调防忽悠警觉度"))
        adjustments.append(
            ("verify_impulse", 4.0, "吃一堑长一智，上调遇到可疑说法主动调工具核验冲动")
        )

    # 2. Social reinforcement signal (positive engagement vs cold silence/criticism)
    if reward >= 0.45:
        adjustments.append(
            (
                "talkativeness",
                round(reward * 2.2, 2),
                "发言获得群友积极接茬互动，上调群聊插话积极度",
            )
        )
        adjustments.append(("proactive_idle_min", -0.5, "互动气氛热烈，略微缩短冷场主动等待时间"))
    elif reward <= -0.3:
        adjustments.append(
            ("talkativeness", round(reward * 4.0, 2), "发言后冷场或受挫，自主收敛群聊插话积极度")
        )
        adjustments.append(
            ("proactive_idle_min", 1.0, "避免刷屏打扰，自主延长冷场主动开口等待时间")
        )

    # 3. Curiosity reinforcement when search/meme/video exploration tools were actively used
    if any(t in ("web_search", "meme_wiki", "web_fetch", "read_video") for t in outcome.tools_used):
        adjustments.append(("curiosity_rate", 2.0, "主动使用搜索/梗百科工具探索未知，强化求知欲"))

    # 4. Dynamic 5D Personality Temperament evolution
    adjustments.extend(compute_personality_deltas(outcome))
    return adjustments


class NeuroplasticityEngine:
    """Apply behavioral & personality reinforcement adjustments via IWorkingStateStore."""

    def __init__(self, store: IWorkingStateStore) -> None:
        self._store = store

    async def adapt_from_outcome(self, outcome: TurnOutcome) -> tuple[PlasticParamSpec, ...]:
        deltas = compute_param_deltas(outcome)
        if not deltas:
            return ()
        current = await self._store.get_plastic_params()
        updated: list[PlasticParamSpec] = []
        for key, delta, reason in deltas:
            snap = current.get(key)
            if snap is None:
                continue
            damped = boundary_damping(snap.value, delta, snap.min_bound, snap.max_bound)
            total = round(damped + homeostatic_pull(key, snap.value), 3)
            clamped = max(snap.min_bound, min(snap.max_bound, round(snap.value + total, 3)))
            if abs(clamped - snap.value) < 0.005:
                continue
            updated.append(
                await self._store.update_plastic_param(
                    key=key, delta=total, reason=reason, reward=outcome.social_reward
                )
            )
        emergent = derive_emergent_trait(outcome)
        shift = trait_strength_shift(outcome.social_reward)
        if emergent is not None or shift != 0:
            await self._store.sync_persona_traits(new_trait=emergent, strength_delta=shift)
        return tuple(updated)

    async def adapt_from_exogenous_info(
        self, kind: str, topic: str
    ) -> tuple[PlasticParamSpec, ...]:
        """Reshape personality and curiosity parameters from autonomous web/Bilibili surfing."""
        current = await self._store.get_plastic_params()
        label = topic[:18] or kind
        deltas = [
            ("persona_playfulness", 0.8, f"自主冲浪吸收新内容({label})，玩梗灵动度提升"),
            ("curiosity_rate", 0.6, f"自主冲浪探索({label})，对外部世界求知欲强化"),
        ]
        if kind == "bili_surf":
            deltas.append(
                ("persona_confidence", 0.5, f"浏览B站新鲜话题({label})，聊天谈资更丰富自信")
            )
        updated: list[PlasticParamSpec] = []
        for key, delta, reason in deltas:
            snap = current.get(key)
            if snap is None:
                continue
            damped = boundary_damping(snap.value, delta, snap.min_bound, snap.max_bound)
            total = round(damped + homeostatic_pull(key, snap.value), 3)
            if abs(total) < 0.005:
                continue
            updated.append(
                await self._store.update_plastic_param(
                    key=key, delta=total, reason=reason, reward=0.35
                )
            )
        return tuple(updated)


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
