"""Extract explicit first-person commitments from outgoing text; no inference."""

from __future__ import annotations

from echomind.domain.models import IntentionItem

_COMMITMENT_MARKERS = (
    "我这就去", "我马上去", "我待会儿", "我待会", "我稍后",
    "我这就", "我马上", "我去群里", "我去说", "我明天",
)
_NEGATIONS = ("不去", "不说", "不想去", "不会去")


def extract_commitments(
    sent_texts: tuple[str, ...], now_ms: int,
) -> tuple[IntentionItem, ...]:
    """Keep only explicit commitment sentences; TTL is left unset until policy is calibrated."""
    found: list[IntentionItem] = []
    for raw in sent_texts:
        text = raw.strip()
        if not text or any(neg in text for neg in _NEGATIONS):
            continue
        if any(marker in text for marker in _COMMITMENT_MARKERS):
            found.append(IntentionItem(
                summary=text[:120], created_at_ms=now_ms, expires_at_ms=0,
            ))
    return tuple(found)
