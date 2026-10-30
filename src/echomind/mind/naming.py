"""Stage 29 A4: single source of truth for the persona's own name and aliases."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BotNaming:
    """Configured self-identity used when rendering prompts."""

    name: str = "回音"
    aliases: tuple[str, ...] = field(default_factory=lambda: ("尾尾",))

    def label(self) -> str:
        return self.name.strip() or "Echo"

    def display(self) -> str:
        extra = tuple(a for a in self.aliases if a and a != self.name)
        return f"{self.label()}（{extra[0]}）" if extra else self.label()


_CURRENT = BotNaming()


def set_bot_naming(naming: BotNaming) -> None:
    """Install the configured identity (called once at bootstrap)."""
    global _CURRENT
    _CURRENT = naming


def bot_naming() -> BotNaming:
    return _CURRENT
