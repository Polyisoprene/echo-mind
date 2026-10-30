"""Stage 39 S39-3: claim ranking and shadow comparison helpers."""

from __future__ import annotations

from echomind.mind.fact_shadow import ClaimView, claim_rank, compare

NOW = 1_800_000_000_000


def _view(subject: str, value: str, *, belief: float = 0.6, age_days: float = 0.0,
          locked: bool = False, predicate: str = "value") -> ClaimView:
    return ClaimView(subject=subject, value=value, predicate=predicate, belief=belief,
                     recorded_at_ms=int(NOW - age_days * 86_400_000), locked=locked)


def test_claim_rank_prefers_recent_and_believed() -> None:
    views = [_view("群主", "A", belief=0.6, age_days=30),
             _view("群主", "B", belief=0.9, age_days=1)]
    ranked = claim_rank(views, "群主", 5, NOW)
    assert ranked[0].startswith("群主：B")


def test_claim_rank_dedupes_per_subject_and_predicate() -> None:
    views = [_view("L", "第一句", predicate="mentioned", age_days=5),
             _view("L", "第二句", predicate="mentioned", age_days=0),
             _view("L", "设定", predicate="value", age_days=0)]
    ranked = claim_rank(views, "L", 10, NOW)
    assert len(ranked) == 2


def test_compare_reports_overlap_and_differences() -> None:
    result = compare(["a", "b", "c"], ["b", "c", "d"])
    assert result["overlap"] == 2 and result["only_claims"] == ["d"]
    assert result["ratio"] == 0.5
