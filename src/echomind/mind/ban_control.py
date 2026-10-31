"""Owner-issued phrase bans: extraction, outbound purge, and self-correction loop."""

from __future__ import annotations

import re

from echomind.domain.models import Percept
from echomind.domain.ports import IPersonaConstraintStore

BAN_PATTERN = re.compile(
    r"(?:不许|不准|不要|别|禁止|不能|少)(?:再)?(?:说|用|带|发|喊|叫|打)(?:那个|这个)?\s*"
    r"[『「\"“']?([\u4e00-\u9fa5A-Za-z0-9]{1,8})[』」\"”']?"
)
BAN_STOPWORDS = frozenset(
    {"话", "我", "你", "他", "她", "了", "吧", "啊", "呀", "哦", "什么", "这个", "那个"}
)
RESIDUE_ONLY_RE = re.compile(r"^[\s，,。.！!？?；;：:~～、]+$")
DUP_PUNCT_RE = re.compile(r"([，,。.！!？?；;])\1+")


def _unique_terms(raw_terms: list[str]) -> tuple[str, ...]:
    kept: list[str] = []
    for raw in raw_terms:
        term = raw.strip()
        if not term or term in BAN_STOPWORDS or term in kept:
            continue
        kept.append(term)
    return tuple(kept)


def extract_new_bans(
    triggers: tuple[Percept, ...], operator_ids: tuple[str, ...] | set[str]
) -> tuple[str, ...]:
    """Extract phrase bans issued by a configured operator (e.g. 说话不许带诶)."""
    if not operator_ids:
        return ()
    texts = [p.text for p in triggers if p.sender_id in operator_ids]
    raw_terms = [raw for text in texts for raw in BAN_PATTERN.findall(text)]
    return _unique_terms(raw_terms)


def purge_banned(text: str, bans: tuple[str, ...]) -> str | None:
    """Strip every banned substring; return None when nothing meaningful is left."""
    cleaned = text
    for ban in bans:
        if ban:
            cleaned = cleaned.replace(ban, "")
    cleaned = DUP_PUNCT_RE.sub(r"\1", cleaned).strip()
    if not cleaned or RESIDUE_ONLY_RE.match(cleaned):
        return None
    return cleaned


def purge_message_batch(
    messages: str | list[str] | tuple[str, ...], bans: tuple[str, ...]
) -> tuple[str, ...]:
    """Purge a single string or message list, dropping fully-stripped entries."""
    raw = [messages] if isinstance(messages, str) else [str(m) for m in messages]
    if not bans:
        return tuple(m.strip() for m in raw if m.strip())
    kept: list[str] = []
    for item in raw:
        survivor = purge_banned(item, bans)
        if survivor:
            kept.append(survivor)
    return tuple(kept)


async def resolve_bans(
    constraints: IPersonaConstraintStore | None,
    triggers: tuple[Percept, ...],
    operator_ids: tuple[str, ...],
    *,
    dry: bool = False,
) -> tuple[str, ...]:
    """Extract operator bans, persist them (unless dry) and return the full list."""
    if constraints is None:
        return ()
    new_bans = extract_new_bans(triggers, operator_ids)
    if not dry:
        for phrase in new_bans:
            await constraints.add_banned_phrase(phrase, "管理员明令禁止的口癖")
    existing = await constraints.get_banned_phrases()
    return tuple(dict.fromkeys([*new_bans, *existing]))
