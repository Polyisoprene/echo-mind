"""Bounded 6D chord cache shared by the cognitive facade and the subconscious probe."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from echomind.mind.subconscious_probe import SubconsciousChordResult

CACHE_LIMIT = 256


def remember_chord(
    cache: dict[str, SubconsciousChordResult], message_id: str, chord: SubconsciousChordResult
) -> None:
    """Store a chord inside a bounded FIFO window so the cache cannot grow unbounded."""
    if not message_id:
        return
    cache[message_id] = chord
    while len(cache) > CACHE_LIMIT:
        cache.pop(next(iter(cache)))
