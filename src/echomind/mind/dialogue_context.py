"""Stage 33: the probe needs the real dialogue, including what she just said.

Per-scope ring buffers: a group and a private chat must not see each other's lines.
"""

from __future__ import annotations

from collections import deque

MAX_LINES = 8
MAX_CHARS = 80


class DialogueContext:
    """Bounded, mixed-direction conversation buffers keyed by chat scope."""

    def __init__(self, limit: int = MAX_LINES) -> None:
        self._limit = limit
        self._lines: dict[str, deque[str]] = {}

    def _buffer(self, scope: str) -> deque[str]:
        if scope not in self._lines:
            self._lines[scope] = deque(maxlen=self._limit)
        return self._lines[scope]

    def add(self, scope: str, speaker: str, text: str) -> None:
        """Append one line to one scope (speaker label kept short, text truncated)."""
        body = " ".join((text or "").split())[:MAX_CHARS]
        if body:
            self._buffer(scope).append(f"{speaker or '?'}: {body}")

    def note(self, scope: str, speaker: str, text: str) -> tuple[str, ...]:
        """Append and return the current window in one call."""
        self.add(scope, speaker, text)
        return self.lines(scope)

    def lines(self, scope: str) -> tuple[str, ...]:
        """Current context window for one scope, oldest first."""
        return tuple(self._lines.get(scope, ()))

    def clear(self, scope: str | None = None) -> None:
        if scope is None:
            self._lines.clear()
        else:
            self._lines.pop(scope, None)
