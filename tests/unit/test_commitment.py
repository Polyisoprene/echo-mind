"""Commitment extraction is explicit and conservative."""

from __future__ import annotations

from echomind.mind.commitment import extract_commitments


def test_explicit_promise_creates_intention() -> None:
    items = extract_commitments(("别催，我这就去群里说",), 100)
    assert len(items) == 1
    assert items[0].summary.startswith("别催")


def test_negated_or_ordinary_sentence_is_ignored() -> None:
    assert extract_commitments(("我不去群里说",), 100) == ()
    assert extract_commitments(("今天吃了饭",), 100) == ()
