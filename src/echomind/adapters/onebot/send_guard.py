"""Outbound message sanitizer & deduplication guard (anti-double-@ & quote merging)."""

from __future__ import annotations

import re
import time

from echomind.domain.models import FrozenValueObject

CQ_AT_PATTERN = re.compile(r"^\s*(?:\[CQ:at,[^\]]+\]\s*)+", re.IGNORECASE)
TEXT_AT_PATTERN = re.compile(
    r"^\s*(?:@[^\s@，,。！!？?：:()（）]+(?:[(（]QQ[:：]\d+[)）])?[\s，,：:]*)+"
)
LEADING_THOUGHT_PAREN_RE = re.compile(
    r"^\s*[（(][^）)\n]*(?:这轮|点我|插嘴|插话|先不|得回|无需|不用回|保持安静)[^）)\n]*[）)]\s*"
)


class SanitizedSendPlan(FrozenValueObject):
    """Immutable outbound send plan after anti-double-@ & reply deduplication."""

    clean_text: str
    effective_reply_mid: str | None = None
    effective_at_uid: str | None = None


def _normalize_opt_id(raw_id: str | None) -> str | None:
    if raw_id is None:
        return None
    val = raw_id.strip()
    return val if val else None


def _strip_leading_mentions(text: str) -> str:
    without_cq = CQ_AT_PATTERN.sub("", text)
    return TEXT_AT_PATTERN.sub("", without_cq).strip()


def sanitize_outbound_text(
    raw_text: str,
    reply_to_mid: str | None = None,
    at_user_id: str | None = None,
    *,
    preserve_both: bool = False,
) -> SanitizedSendPlan:
    """Strip duplicate leading @mentions when native reply or at segment is attached."""
    eff_reply = _normalize_opt_id(reply_to_mid)
    raw_at = _normalize_opt_id(at_user_id)
    raw_text = LEADING_THOUGHT_PAREN_RE.sub("", raw_text).strip()
    # NapCat reply segment already includes a native @ to the quoted author unless @ing a 3rd party
    eff_at = raw_at if (preserve_both or eff_reply is None) else None
    has_native_mention = (eff_reply is not None) or (eff_at is not None)

    if not has_native_mention:
        return SanitizedSendPlan(clean_text=raw_text.strip())

    stripped = _strip_leading_mentions(raw_text)
    final_text = stripped if (stripped or eff_at is not None) else raw_text.strip()
    if eff_at is not None and final_text and not final_text.startswith(" "):
        final_text = f" {final_text}"

    return SanitizedSendPlan(
        clean_text=final_text,
        effective_reply_mid=eff_reply,
        effective_at_uid=eff_at,
    )


class OutboundDeduplicator:
    """Sliding-window deduplicator preventing accidental double-sends within window_ms."""

    def __init__(self, window_ms: int = 8000) -> None:
        self._window_ms = window_ms
        self._recent: dict[str, int] = {}

    def is_duplicate(self, chat_key: str, payload_key: str, now_ms: int | None = None) -> bool:
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        full_key = f"{chat_key}::{payload_key.strip()}"
        last_ts = self._recent.get(full_key)
        if last_ts is not None and (now - last_ts) < self._window_ms:
            return True
        self._recent[full_key] = now
        return False
