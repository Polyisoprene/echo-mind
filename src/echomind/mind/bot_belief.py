"""Stage 31 S31-2: she forms a belief about who is a bot from her own semantic memory.

No hardcoded roster: the belief is extracted from facts she already stored (or an operator
phrased in natural language), scored by confidence, and capped by evidence quality.
"""

from __future__ import annotations

import re

BOT_KEYWORDS = ("机器人", "bot", "自动回复", "脚本", "人工智能")
THROTTLE_HINTS = ("不要频繁", "别频繁", "会刷屏", "刷屏", "少接", "别接")
_ID_RE = re.compile(r"(?:QQ[:：\s]*)?(\d{6,12})(?!\d)")
# 只认"某 id 是机器人"这种断言；"搭建/做/写/教程"是在造机器人，不是身份陈述。
_ASSERT_RE = re.compile(
    r"(?:是|为|属于|也是)\s*(?:一个|个)?\s*(?:机器人|bot|AI|人工智能|自动回复|脚本)", re.I
)
_BUILD_RE = re.compile(r"搭建|做一个|自己弄|写一个|造一个|教程|部署|参考|想弄|开个")

_BELIEFS: dict[str, float] = {}


def extract_ids(*texts: str) -> tuple[str, ...]:
    """Pull every plausible QQ id out of a fact's subject/text (deduplicated, ordered)."""
    found: list[str] = []
    for text in texts:
        found.extend(m.group(1) for m in _ID_RE.finditer(text or ""))
    return tuple(dict.fromkeys(found))


def _is_assertion(subject: str, blob: str) -> bool:
    """True when the fact claims someone IS a bot (not that someone builds one)."""
    if subject.startswith("自组织图式"):
        return False
    if not any(word in blob.lower() for word in BOT_KEYWORDS):
        return False
    return not _BUILD_RE.search(blob)


def _asserted_ids(blob: str) -> list[str]:
    """Ids that sit inside an identity assertion window."""
    kept: list[str] = []
    for uid in extract_ids(blob):
        pos = blob.find(uid)
        if _ASSERT_RE.search(blob[max(0, pos - 30): pos + 30]):
            kept.append(uid)
    return kept


def score_fact(subject: str, fact_text: str, confidence: float = 1.0) -> dict[str, float]:
    """Score one fact into per-id bot beliefs (empty when it is not an identity assertion)."""
    blob = f"{subject} {fact_text}"
    if not _is_assertion(subject, blob):
        return {}
    base = 0.65
    if any(hint in blob for hint in THROTTLE_HINTS):
        base += 0.20
    if "是机器人" in blob or "不是人" in blob:
        base += 0.10
    weight = max(0.0, min(1.0, confidence))
    score = min(1.0, base * (0.6 + 0.4 * weight))
    return {uid: round(score, 2) for uid in _asserted_ids(blob)}


def rebuild(facts: tuple[tuple[str, str, float], ...]) -> dict[str, float]:
    """Fold every fact into the strongest per-sender belief (max, never sum)."""
    merged: dict[str, float] = {}
    for subject, fact_text, confidence in facts:
        for uid, value in score_fact(subject, fact_text, confidence).items():
            merged[uid] = round(max(merged.get(uid, 0.0), value), 2)
    return merged


def set_beliefs(beliefs: dict[str, float]) -> None:
    """Replace the current per-sender belief table."""
    _BELIEFS.clear()
    _BELIEFS.update({k: max(0.0, min(1.0, v)) for k, v in beliefs.items()})


def apply_belief(sender_id: str) -> float:
    """Bot belief for one sender; 0.0 means "treated as human"."""
    return _BELIEFS.get(sender_id, 0.0)
