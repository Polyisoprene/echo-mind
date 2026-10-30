"""Stage 30 S30-1: the single source of truth for the 7D persona vector.

Every consumer (storage defaults, salience scoring, plasticity baselines, prompt rendering)
must read these values; no module may restate them as literals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaSpec:
    """Declared default and bounds of one personality dimension."""

    key: str
    default: float
    min_bound: float
    max_bound: float
    description: str


PERSONA_SPECS: dict[str, PersonaSpec] = {
    spec.key: spec
    for spec in (
        PersonaSpec("persona_warmth", 65.0, 15.0, 98.0,
                    "性格维度：温柔粘人度 vs 清冷慢热度"),
        PersonaSpec("persona_tsundere", 62.0, 10.0, 95.0,
                    "性格维度：依恋回避/傲娇嘴硬防备指数"),
        PersonaSpec("persona_playfulness", 58.0, 15.0, 95.0,
                    "性格维度：古灵精怪玩梗吐槽度"),
        PersonaSpec("persona_possessiveness", 75.0, 20.0, 98.0,
                    "性格维度：依恋焦虑/对在意之人的独占护食度"),
        PersonaSpec("persona_confidence", 55.0, 15.0, 95.0,
                    "性格维度：社交自信笃定度 vs 害羞胆怯度"),
        PersonaSpec("persona_guile", 52.0, 10.0, 95.0,
                    "HEXACO H轴反向：狡黠度/小机灵鬼撒谎与反忽悠倾向"),
        PersonaSpec("persona_defiance", 48.0, 10.0, 95.0,
                    "Brehm逆反/HEXACO A轴反向：小刺头叛逆度"),
    )
}


def persona_default(key: str) -> float:
    """Declared baseline for one dimension (raises for unknown keys)."""
    return PERSONA_SPECS[key].default
