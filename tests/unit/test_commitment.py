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


def test_explicit_chat_key_is_kept_as_target() -> None:
    items = extract_commitments(("我这就去 group:123 说",), 100)
    assert items[0].target_chat_key == "group:123"
    assert extract_commitments(("我这就去群里说",), 100)[0].target_chat_key == ""


def test_satiate_snapshot_keeps_new_commitment() -> None:
    from echomind.domain.models import WorkingSnapshot
    from echomind.mind.turn_mutations import satiate_snapshot

    updated = satiate_snapshot(
        WorkingSnapshot(scope_key="global"),
        ("我这就去 group:123 说",), (), 100,
    )
    assert len(updated.intentions) == 1
    assert updated.intentions[0].target_chat_key == "group:123"
