"""Domain value object holding per-member interaction counters for earned bond depth."""

from __future__ import annotations

from echomind.domain.models import FrozenValueObject


class BondDepthStats(FrozenValueObject):
    """Persisted per-member interaction counters used to derive earned bond depth."""

    chat_key: str
    user_id: str
    msgs: int = 0
    her_msgs: int = 0
    replies_to_them: int = 0
    responded_to_her: int = 0
    sessions: int = 0
    impact_sum: float = 0.0
    impact_n: int = 0
    betrayals: int = 0
    updated_ms: int = 0


class BondFeatures(FrozenValueObject):
    """Normalized [0, 1] bond-depth features derived from persisted counters."""

    frequency: float = 0.0
    diversity: float = 0.0
    responsivity: float = 0.0
    reciprocity: float = 0.0
    impact: float = 0.0
    betrayal: float = 0.0
