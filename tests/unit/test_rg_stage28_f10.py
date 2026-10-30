"""Stage 28 F10 guard: aversion is chord-driven; taboo text never substring-matches messages."""

from __future__ import annotations

import inspect

from echomind.mind import shadow_appraisal


def test_rg_f10_aversion_signature_is_chord_only() -> None:
    params = list(inspect.signature(shadow_appraisal._check_aversion).parameters)
    assert params == ["joined", "chord"], f"unexpected signature: {params}"
    assert not hasattr(shadow_appraisal, "_extract_taboo_texts")


def test_rg_f10_taboo_sentence_does_not_trigger_aversion() -> None:
    taboo_sentence = "极度讨厌别人用命令语气拿我当没有感情的工具人使唤"
    matched = shadow_appraisal._check_aversion(taboo_sentence, None)
    assert matched == "", "a taboo sentence in the message must not trigger deterministic aversion"
