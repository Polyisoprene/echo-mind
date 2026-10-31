"""Read-only health classification for the trait evolution pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HealthStatus = Literal[
    "no_active", "waiting_turn", "shadow_missing_trait", "no_causal_links", "ok"
]


@dataclass(frozen=True)
class TraitHealth:
    active_traits: int
    shadow_since_activation: int
    nonempty_shadow: int
    causal_links: int
    latest_turn_ms: int

    @property
    def status(self) -> HealthStatus:
        if self.active_traits == 0:
            return "no_active"
        if self.shadow_since_activation == 0:
            return "waiting_turn"
        if self.nonempty_shadow == 0:
            return "shadow_missing_trait"
        if self.causal_links == 0:
            return "no_causal_links"
        return "ok"
