"""Stage 33: the probe needs the real dialogue, including what she just said.

Feeding only inbound gate-log lines made follow-ups look like ambient chatter: the probe had
no "上一句" to connect them to. This ring buffer keeps the last few turns of both sides.
"""

from __future__ import annotations

from collections import deque

MAX_LINES = 8
MAX_CHARS = 80


class DialogueContext:
    """Bounded, mixed-direction conversation buffer for probe context."""

    def __init__(self, limit: int = MAX_LINES) -> None:
        self._lines: deque[str] = deque(maxlen=limit)

    def add(self, speaker: str, text: str) -> None:
        """Append one line (speaker label kept short, text truncated)."""
        body = " ".join((text or "").split())[:MAX_CHARS]
        if body:
            self._lines.append(f"{speaker or '?'}: {body}")

    def note(self, speaker: str, text: str) -> tuple[str, ...]:
        """Append and return the current window in one call."""
        self.add(speaker, text)
        return self.lines()

    def lines(self) -> tuple[str, ...]:
        """Current context window, oldest first."""
        return tuple(self._lines)

    def clear(self) -> None:
        self._lines.clear()
