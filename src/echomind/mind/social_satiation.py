"""Stage 31: social satiation — she gets (softly) tired of one interlocutor, then recovers.

No blacklist, no quota: willingness decays with repeated replies to the same sender and
recovers with time, remaining strictly above `floor`. Real senders (bot_like = 0) are
never affected.

param: convention:s31-recovery - tau=1800 s matches the observed burst structure
(median intra-burst gap 8 s, inter-burst 280 s; >20 min gaps only 2%).
param: fit:s31-burst-cap - alpha=0.40 is derived from the target "8 exchanges -> <=4".
param: fit:s31-daily-turns - floor=0.08 is derived from the target "58 -> <=18 turns/day".
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from dataclasses import dataclass, field

from echomind.domain.models import AttentionDecision, Percept

logger = logging.getLogger(__name__)

# param: data:satiation-tau - median inter-burst gap 247 s (95% CI 223-271, n=1,835);
# refit with scripts/fit_satiation_tau.py. Shadow: suppression 34.6% -> 17.2%.
TAU_S = 247.0
ALPHA = 0.40
FLOOR = 0.08
GAMMA = 0.5


def willingness(h: float, bot_like: float, floor: float = FLOOR) -> float:
    """Probability-like reply urge for the given habituation and bot belief."""
    if bot_like <= 0.0:
        return 1.0
    p = floor + (1.0 - floor) * (1.0 - max(0.0, min(1.0, h)) * min(1.0, bot_like))
    return max(floor, min(1.0, p))


def _uniform(key: str) -> float:
    """Deterministic uniform draw in [0, 1) — same key always gives the same draw."""
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") / float(1 << 64)


def combine_with_cold_shoulder(p_satiation: float, p_cold_shoulder: float) -> float:
    """Lenient composition: being tired and being annoyed must not multiply into silence."""
    return max(p_satiation, p_cold_shoulder)


@dataclass
class SatiationState:
    """Per-(chat, sender) habituation with spontaneous recovery."""

    tau_s: float = TAU_S
    alpha: float = ALPHA
    floor: float = FLOOR
    gamma: float = GAMMA
    _h: dict[tuple[str, str], float] = field(default_factory=dict)
    _last: dict[tuple[str, str], int] = field(default_factory=dict)

    def _decayed(self, key: tuple[str, str], now_ms: int) -> float:
        last = self._last.get(key)
        h = self._h.get(key, 0.0)
        if last is None:
            return 0.0
        return h * math.exp(-max(0.0, (now_ms - last) / 1000.0) / self.tau_s)

    def willingness(self, chat: str, sender: str, now_ms: int, bot_like: float) -> float:
        """Current reply urge (also decays the stored state lazily)."""
        h = self._decayed((chat, sender), now_ms)
        return willingness(h, bot_like, self.floor)

    def record_reply(self, chat: str, sender: str, now_ms: int) -> None:
        """Deepen habituation after she actually answered this sender."""
        key = (chat, sender)
        h = self._decayed(key, now_ms)
        self._h[key] = min(0.999, h + self.alpha * (1.0 - h))
        self._last[key] = now_ms

    def novelty(self, chat: str, sender: str, novelty: float, now_ms: int) -> None:
        """Dishabituation: a genuinely new topic discounts the accumulated fatigue."""
        key = (chat, sender)
        h = self._decayed(key, now_ms)
        self._h[key] = max(0.0, h * (1.0 - self.gamma * max(0.0, min(1.0, novelty))))
        self._last[key] = now_ms


def mode() -> str:
    """off (default) | shadow (log only) | on."""
    return os.getenv("ECHOMIND_SATIATION", "off").strip().lower()


def adjust_decision(
    decision: AttentionDecision, percept: Percept, state: SatiationState, bot_like: float
) -> AttentionDecision:
    """Soften a tier>=2 wake decision; inert unless the feature is enabled."""
    if mode() == "off" or decision.tier < 2 or bot_like <= 0.0:
        return decision
    p = state.willingness(percept.chat_key, percept.sender_id, percept.timestamp_ms, bot_like)
    if mode() == "shadow":
        logger.info("satiation shadow chat=%s sender=%s belief=%.2f p=%.2f",
                    percept.chat_key, percept.sender_id, bot_like, p)
        return decision
    draw = _uniform(f"{percept.chat_key}:{percept.sender_id}:{percept.timestamp_ms}")
    if draw < p:  # keep the turn with probability p (the floor guarantees p > 0)
        return decision
    return decision.model_copy(
        update={
            "should_wake": False,
            "tier": 0,
            "salience_score": round(decision.salience_score * p, 3),
            "reason": f"社交习惯化·意愿{p:.2f}",
        }
    )
