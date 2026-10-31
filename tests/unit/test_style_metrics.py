"""Deterministic style metrics used after the realism change."""

from __future__ import annotations

import pytest

from echomind.mind.style_metrics import summarize, text_flags


def test_flags_detect_long_explain_and_roleplay() -> None:
    flags = text_flags("因为隐私规则不能随便给（笑）", long_chars=5)
    assert flags["explain"] is True
    assert flags["roleplay"] is True
    assert flags["long"] is True


def test_summarize_rates() -> None:
    summary = summarize(["好", "因为规则不能给", "（哼）"], long_chars=5)
    assert summary["n"] == 3
    assert summary["long_rate"] == pytest.approx(1 / 3, abs=0.001)
    assert summary["explain_rate"] == pytest.approx(1 / 3, abs=0.001)
    assert summary["roleplay_rate"] == pytest.approx(1 / 3, abs=0.001)
