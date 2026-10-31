"""Conservative typed-relation extraction from fact text (P2)."""

from __future__ import annotations

import re
from dataclasses import dataclass

ENTITY = r"[A-Za-z][A-Za-z0-9_]{0,31}|\d{5,12}|[\u4e00-\u9fa5]{2,12}"
_PATTERNS: tuple[tuple[str, str], ...] = (
    ("works_at", rf"^(?P<s>{ENTITY})\s*在\s*(?P<o>{ENTITY})\s*(?:工作|上班)"),
    ("friend", rf"^(?P<s>{ENTITY})\s*是\s*(?P<o>{ENTITY})\s*的\s*朋友"),
    ("sibling", rf"^(?P<s>{ENTITY})\s*是\s*(?P<o>{ENTITY})\s*的\s*(?:哥哥|弟弟|姐姐|妹妹)"),
    ("gave_to", rf"^(?P<s>{ENTITY})\s*把.*?给(?:了)?\s*(?P<o>{ENTITY})"),
    ("alias", r"QQ:(?P<s>\d{5,12})\s*(?:的群昵称是|的群友是)\s*"
              r"[「『\"']?(?P<o>[^\s，。；」』\"']{1,20})"),
)
RELATION_CONFIDENCE = 1.0


@dataclass(frozen=True)
class RelationCandidate:
    subject: str
    predicate: str
    object: str
    confidence: float = RELATION_CONFIDENCE


def extract(subject: str, text: str) -> tuple[RelationCandidate, ...]:
    """Extract only high-precision patterns; unknown text yields nothing."""
    clean = text.strip()
    if not clean:
        return ()
    found: list[RelationCandidate] = []
    for predicate, pattern in _PATTERNS:
        match = re.match(pattern, clean)
        if match is None:
            continue
        subj, obj = match.group("s").strip(), match.group("o").strip()
        if subj and obj and subj != obj:
            found.append(RelationCandidate(subj, predicate, obj))
    return tuple(found)


__all__ = ["RelationCandidate", "extract"]
