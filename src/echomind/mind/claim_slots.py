"""Explicit person-trait slot inference; single-value slots only."""

from __future__ import annotations

SINGLE_SLOTS = frozenset({
    "person.nickname", "person.gender", "person.birthday", "person.age",
    "person.owner", "person.city", "person.job", "person.species",
    "person.relationship",
})

_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("person.nickname", ("群昵称", "昵称是", "外号", "nickname")),
    ("person.gender", ("是男性", "是女性", "性别是", "gender")),
    ("person.birthday", ("生日是", "出生于", "birthday")),
    ("person.age", ("年龄是", "今年", "age")),
    ("person.owner", ("主人是", "唯一主人", "master is")),
    ("person.city", ("住在", "定居", "搬到", "living in", "city")),
    ("person.job", ("职业是", "工作是", "从事", "occupation")),
    ("person.species", ("物种", "species")),
    ("person.relationship", ("恋爱", "单身", "已婚", "relationship")),
)


def infer_slot(subject: str, value: str) -> str:
    """Return one single-value slot only when exactly one pattern matches."""
    if not subject.strip() or not value.strip():
        return ""
    text = value.lower()
    hits = [slot for slot, words in _PATTERNS if any(word in text for word in words)]
    return hits[0] if len(hits) == 1 else ""


def is_single(slot_key: str) -> bool:
    return slot_key in SINGLE_SLOTS
