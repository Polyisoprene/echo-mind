"""Explicit person-trait slot inference; single-value slots only."""

from __future__ import annotations

SINGLE_SLOTS = frozenset({
    "person.qq", "person.gender", "person.birthday", "person.age",
})

_META_SUBJECTS = ("自组织图式", "本群", "群规", "群公告", "回音", "记忆")
_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("person.qq", ("qq号是", "qq号为", "qq号：")),
    ("person.gender", ("是男性", "是女性", "性别是", "gender")),
    ("person.birthday", ("生日是", "出生于", "birthday")),
    ("person.age", ("年龄是", "今年")),
)


def _person_subject(subject: str) -> bool:
    text = subject.strip()
    return bool(text) and not any(text.startswith(prefix) for prefix in _META_SUBJECTS)


def _slot_matches(text: str) -> list[str]:
    return [slot for slot, words in _PATTERNS if any(word in text for word in words)]


def infer_slot(subject: str, value: str) -> str:
    """Return one single-value slot only when exactly one pattern matches."""
    if not _person_subject(subject) or not value.strip():
        return ""
    text = value.split("此前曾是", 1)[0].lower()
    hits = _slot_matches(text)
    if len(hits) != 1:
        return ""
    return hits[0]


def is_single(slot_key: str) -> bool:
    return slot_key in SINGLE_SLOTS
