"""A-lane replay probe: recorded 6D chords, zero LLM calls, deterministic selection."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from echomind.domain.models import Percept, SocialBondProfile
from echomind.mind.subconscious_probe import SubconsciousChordResult, parse_chord_json


def _load_fixture(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "default" not in raw:
        raise ValueError(f"invalid chord fixture: {path}")
    return raw


def _to_result(data: Any) -> SubconsciousChordResult | None:
    return parse_chord_json(json.dumps(data, ensure_ascii=False))


class ChordFixtureProbe:
    """Stand-in for SubconsciousChordProbe that replays recorded chords from a fixture file."""

    def __init__(self, fixture_path: Path | str) -> None:
        fixture = _load_fixture(fixture_path)
        raw_rules = fixture.get("rules")
        self._rules: list[tuple[re.Pattern[str], Any]] = [
            (re.compile(str(r.get("match", ""))), r.get("chord"))
            for r in (raw_rules if isinstance(raw_rules, list) else [])
            if isinstance(r, dict) and r.get("match")
        ]
        self._default = fixture["default"]
        self.calls = 0
        self.clock: dict[str, int] = {}

    async def appraise(
        self,
        percept: Percept,
        recent_lines: tuple[str, ...] = (),
        bond: SocialBondProfile | None = None,
        timeout_s: float = 1.2,
    ) -> SubconsciousChordResult | None:
        """Return the first recorded chord whose pattern matches the message text."""
        _ = (recent_lines, bond, timeout_s)
        self.calls += 1
        for pattern, chord in self._rules:
            if pattern.search(percept.text):
                return _to_result(chord)
        return _to_result(self._default)
