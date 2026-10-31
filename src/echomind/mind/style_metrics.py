"""Deterministic reply-style metrics for post-change monitoring."""

from __future__ import annotations

import re
from typing import Any

_EXPLAIN = ("因为", "所以", "不能", "隐私", "规则", "需要", "建议", "可以", "但是")


def text_flags(text: str, long_chars: int = 40) -> dict[str, Any]:
    sentences = [s for s in re.split(r"[。！？!?]+", text) if s.strip()]
    return {
        "length": len(text),
        "long": len(text) > long_chars,
        "explain": any(word in text for word in _EXPLAIN),
        "roleplay": ("（" in text or "(" in text),
        "multi_question": (text.count("？") + text.count("?")) > 1,
        "sentences": len(sentences),
    }


def summarize(texts: list[str], long_chars: int = 40) -> dict[str, Any]:
    if not texts:
        return {"n": 0, "avg_len": 0.0, "long_rate": 0.0, "explain_rate": 0.0,
                "roleplay_rate": 0.0, "multi_question_rate": 0.0}
    flags = [text_flags(text, long_chars) for text in texts]
    n = len(flags)
    return {
        "n": n,
        "avg_len": round(sum(item["length"] for item in flags) / n, 1),
        "long_rate": round(sum(item["long"] for item in flags) / n, 3),
        "explain_rate": round(sum(item["explain"] for item in flags) / n, 3),
        "roleplay_rate": round(sum(item["roleplay"] for item in flags) / n, 3),
        "multi_question_rate": round(sum(item["multi_question"] for item in flags) / n, 3),
    }


__all__ = ["summarize", "text_flags"]
