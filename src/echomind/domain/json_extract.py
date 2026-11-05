"""Tolerant extraction of one JSON object from free-form LLM output.

Models routinely wrap JSON in prose, markdown fences, or a reasoning trace that
itself contains braces. A greedy `\\{[\\s\\S]*\\}` regex spans from the first `{`
to the last `}`, so any trailing text (or a second object) makes the whole blob
unparseable. This module instead walks the text, tracks brace depth while
honouring string literals and escapes, and returns the first *balanced* object
that actually parses.
"""

from __future__ import annotations

import json
from typing import Any

FENCE = "```"


def _advance_in_string(char: str, escaped: bool) -> tuple[bool, bool]:
    """Step through one character of a string literal; returns (in_string, escaped)."""
    if escaped:
        return True, False
    if char == "\\":
        return True, True
    return (False, False) if char == '"' else (True, False)


_DEPTH_DELTA = {'{': 1, '}': -1}


def _balanced_end(text: str, begin: int) -> int | None:
    """Return the index just past the `}` matching the `{` at `begin`, or None."""
    depth = 0
    in_string = False
    escaped = False
    for idx in range(begin, len(text)):
        char = text[idx]
        if in_string:
            in_string, escaped = _advance_in_string(char, escaped)
            continue
        if char == '"':
            in_string = True
            continue
        depth += _DEPTH_DELTA.get(char, 0)
        if depth == 0 and char == "}":
            return idx + 1
    return None


def _try_load(blob: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(blob)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _candidate_at(text: str, begin: int) -> dict[str, Any] | None:
    """Parse the balanced object starting at `begin`; None if unbalanced or invalid."""
    end = _balanced_end(text, begin)
    if end is None:
        return None
    return _try_load(text[begin:end])


def extract_json_object(raw: str) -> dict[str, Any] | None:
    """Return the first parseable JSON object embedded in `raw`, else None.

    Handles: leading prose, markdown fences, trailing commentary, stray
    unbalanced braces before the real payload, braces inside string values,
    and multiple objects (returns the first one that parses).
    """
    if not raw:
        return None
    text = raw.replace(FENCE, " ")
    cursor = text.find("{")
    while cursor >= 0:
        parsed = _candidate_at(text, cursor)
        if parsed is not None:
            return parsed
        # This opening brace never balanced, or balanced but was not valid JSON:
        # move to the next candidate opening brace and try again.
        cursor = text.find("{", cursor + 1)
    return None


__all__ = ["extract_json_object"]
