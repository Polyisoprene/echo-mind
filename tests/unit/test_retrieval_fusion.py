"""RRF: consensus across lexical and semantic rankings wins."""

from __future__ import annotations

from echomind.mind.retrieval_fusion import rrf_fuse


def test_rrf_prefers_the_consensus_item() -> None:
    assert rrf_fuse(((1, 2, 3), (1, 3, 2)))[0] == 1


def test_rrf_handles_empty_and_single_lists() -> None:
    assert rrf_fuse(()) == ()
    assert rrf_fuse(((4, 2),)) == (4, 2)
