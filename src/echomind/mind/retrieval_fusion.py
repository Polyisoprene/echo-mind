"""Reciprocal Rank Fusion for lexical and semantic memory rankings (M3)."""

from __future__ import annotations

from collections import defaultdict

RRF_K = 60


def rrf_fuse(rankings: tuple[tuple[int, ...], ...], k: int = RRF_K) -> tuple[int, ...]:
    """Fuse rank lists into one order; higher score wins, id breaks ties."""
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] += 1.0 / (k + rank)
    return tuple(sorted(scores, key=lambda item: (-scores[item], item)))


__all__ = ["RRF_K", "rrf_fuse"]
