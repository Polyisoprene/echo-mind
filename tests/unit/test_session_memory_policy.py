"""Cross-session recall is source/audience-aware, not a global bypass."""

from __future__ import annotations

from echomind.mind.session_memory_policy import RecallRequest, can_recall_across_sessions


def test_same_session_always_recalls() -> None:
    assert can_recall_across_sessions(RecallRequest("group:a", "group:a", "secret"))


def test_public_and_group_cross_session_only_without_audience_restriction() -> None:
    assert can_recall_across_sessions(RecallRequest("group:a", "group:b", "public"))
    assert can_recall_across_sessions(RecallRequest("group:a", "group:b", "group"))
    assert not can_recall_across_sessions(
        RecallRequest("group:a", "group:b", "group", ("group:c",))
    )


def test_private_and_secret_never_cross_session() -> None:
    assert not can_recall_across_sessions(RecallRequest("private:a", "group:b", "private"))
    assert not can_recall_across_sessions(RecallRequest("group:a", "group:b", "secret"))
