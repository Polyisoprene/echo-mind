"""Small facade accessors kept out of the line budget."""

from __future__ import annotations

from typing import Any

from echomind.mind.chord_cache import remember_chord
from echomind.mind.semantic_memory import SemanticMemoryRetriever
from echomind.mind.subconscious_probe import SubconsciousChordProbe, SubconsciousChordResult


class FacadeAccessors:
    _last_active_ms: int
    _sub_probe: SubconsciousChordProbe | None
    _chord_cache: dict[str, SubconsciousChordResult]
    _gate_log: list[dict[str, Any]]
    _semantic: SemanticMemoryRetriever | None = None

    @property
    def last_active_ms(self) -> int:
        return self._last_active_ms

    @property
    def recent_gate_log(self) -> list[dict[str, Any]]:
        return list(reversed(self._gate_log))

    def set_subconscious_probe(self, probe: SubconsciousChordProbe | None) -> None:
        self._sub_probe = probe

    def set_semantic_retriever(self, retriever: SemanticMemoryRetriever) -> None:
        self._semantic = retriever

    def cache_chord(self, message_id: str, chord: SubconsciousChordResult) -> None:
        remember_chord(self._chord_cache, message_id, chord)


__all__ = ["FacadeAccessors"]
