"""Directional entity-order guard for role-reversal queries (A->B vs B->A)."""

from __future__ import annotations

import re
from itertools import combinations

_ENTITY_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}|\d{5,12}")


def entities(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(m.group(0).lower() for m in _ENTITY_RE.finditer(text)))


def order_score(query: str, fact: str) -> float:
    """+1 same relative order, -1 reversed, 0 when fewer than two shared entities."""
    q, f = entities(query), entities(fact)
    q_pos = {name: index for index, name in enumerate(q)}
    f_pos = {name: index for index, name in enumerate(f)}
    common = [name for name in q if name in f_pos]
    if len(common) < 2:
        return 0.0
    pairs = list(combinations(common, 2))
    same = sum(
        1 for left, right in pairs
        if (q_pos[left] - q_pos[right]) * (f_pos[left] - f_pos[right]) > 0
    )
    total = len(pairs)
    return (2 * same - total) / max(1, total)


__all__ = ["entities", "order_score"]
