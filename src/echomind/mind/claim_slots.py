"""Explicit person-trait slot inference; single-value slots only."""

from __future__ import annotations

SINGLE_SLOTS = frozenset({
    "person.nickname", "person.gender", "person.birthday", "person.age",
    "person.owner", "person.city", "person.job", "person.species",
    "person.relationship",
})

_META_SUBJECTS = ("自组织图式", "本群", "群规", "群公告", "回音", "记忆")
_GENDER_WORDS = ("男的", "女的", "男性", "女性")

_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("person.nickname", ("群昵称", "昵称是", "昵称是「", "nickname")),
    ("person.gender", ("是男性", "是女性", "性别是", "gender")),
    ("person.birthday", ("生日是", "出生于", "birthday")),
    ("person.age", ("年龄是", "今年")),
    ("person.owner", ("主人是", "唯一主人", "master is")),
    ("person.city", ("住在", "定居", "living in", "city")),
    ("person.job", ("职业是", "工作是", "从事", "occupation")),
    ("person.species", ("物种", "species")),
    ("person.relationship", ("恋爱", "单身", "已婚", "relationship")),
)


def _person_subject(subject: str) -> bool:
    text = subject.strip()
    return bool(text) and not any(text.startswith(prefix) for prefix in _META_SUBJECTS)


def _slot_matches(text: str) -> list[str]:
    return [slot for slot, words in _PATTERNS if any(word in text for word in words)]


def _slot_valid(slot: str, text: str) -> bool:
    if slot == "person.owner" and any(word in text for word in _GENDER_WORDS):
        return False
    bad_city = slot == "person.city" and any(
        word in text for word in ("电脑", "心里", "里")
    )
    return not bad_city


def infer_slot(subject: str, value: str) -> str:
    """Return one single-value slot only when exactly one pattern matches."""
    if not _person_subject(subject) or not value.strip():
        return ""
    text = value.lower()
    hits = _slot_matches(text)
    if len(hits) != 1:
        return ""
    return hits[0] if _slot_valid(hits[0], text) else ""


def is_single(slot_key: str) -> bool:
    return slot_key in SINGLE_SLOTS
