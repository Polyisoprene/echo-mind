"""M3.2 Ebbinghaus Dual-Tier Memory Decay & Relevance Recall Policy (Pure Math Strategy)."""

from __future__ import annotations

import math
import re
from typing import Literal

from echomind.domain.models import EpisodicCard, Percept, SemanticFact
from echomind.mind.cybernetics import compute_associative_flotation_boosts
from echomind.mind.recall_types import RecalledMemoryItem

CLEAR_THRESHOLD = 0.55
FUZZY_THRESHOLD = 0.22
MS_PER_HOUR = 3_600_000.0
TOKEN_RE = re.compile(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]{2,}")
QQ_NUM_RE = re.compile(r"\d{6,12}")


def tokenize_query(text: str) -> frozenset[str]:
    """Extract overlapping Chinese 2-grams and alphanumeric words."""
    tokens: set[str] = set()
    for chunk in TOKEN_RE.findall(text.lower()):
        if chunk.isascii():
            tokens.add(chunk)
        else:
            tokens.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return frozenset(tokens)


def compute_retention(card: EpisodicCard, now_ms: int) -> float:
    """Compute Ebbinghaus retention R(t) = exp(-dt / S) guaranteed in [0.0, 1.0]."""
    if card.pinned:
        return 1.0
    anchor_ms = max(card.timestamp_ms, card.last_recalled_ms)
    elapsed_hours = max(0.0, (now_ms - anchor_ms) / MS_PER_HOUR)
    # Stability S (in hours) scales exponentially with importance (1..5) and rehearsals
    base_stability = 6.0 * (1.8 ** (card.importance - 1.0))
    rehearsal_boost = 1.6 ** min(card.rehearsals, 12)
    stability_hours = max(1.0, base_stability * rehearsal_boost)
    retention = math.exp(-elapsed_hours / stability_hours)
    return max(0.0, min(1.0, retention))


def _relevance_score(
    card: EpisodicCard, query_tokens: frozenset[str], active_uids: frozenset[str]
) -> float:
    card_tokens = tokenize_query(f"{card.summary} {card.key_detail}")
    overlap = len(query_tokens & card_tokens)
    participant_hit = any(p in active_uids for p in card.participants)
    return overlap * 1.5 + (1.2 if participant_hit else 0.0) + (0.8 if card.pinned else 0.0)


def recall_episodic_memories(
    cards: tuple[EpisodicCard, ...],
    query_text: str,
    active_user_ids: tuple[str, ...],
    now_ms: int,
    top_k: int = 5,
) -> tuple[RecalledMemoryItem, ...]:
    """Recall and rank episodic memories into 'clear' (>=55%) vs 'fuzzy' (22%~55%) tiers."""
    if not cards:
        return ()
    q_tokens = tokenize_query(query_text)
    u_set = frozenset(active_user_ids)
    flotation = compute_associative_flotation_boosts(cards, query_text, active_user_ids)
    scored: list[tuple[float, RecalledMemoryItem]] = []

    for card in cards:
        ret = compute_retention(card, now_ms)
        if ret < FUZZY_THRESHOLD:
            continue
        clarity: Literal["clear", "fuzzy"] = "clear" if ret >= CLEAR_THRESHOLD else "fuzzy"
        rel = _relevance_score(card, q_tokens, u_set)
        ppr_boost = flotation.get(card.card_id, 0.0) * 3.0
        rank_score = ret * 2.0 + rel + (card.importance * 0.3) + ppr_boost
        scored.append((rank_score, RecalledMemoryItem(card=card, retention=ret, clarity=clarity)))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return tuple(item for _, item in scored[:top_k])


def format_recalled_item(item: RecalledMemoryItem) -> str:
    """Render a recalled memory item according to its clarity tier."""
    pct = round(item.retention * 100)
    if item.clarity == "clear" and item.card.key_detail:
        return f"- [清晰({pct}%)] {item.card.summary} 【细节锚点：{item.card.key_detail}】"
    return f"- [模糊印象({pct}%·细节已淡忘)] 大概记得：{item.card.summary}"


FACT_RECENCY_HALF_LIFE_DAYS = 30.0
FACT_RECENCY_WEIGHT = 4.0


def fact_recency(
    event_time_ms: int, now_ms: int, half_life_days: float = FACT_RECENCY_HALF_LIFE_DAYS
) -> float:
    """Exponential recency in [0, 1]; 0 when the event time is unknown."""
    if not event_time_ms or not now_ms or event_time_ms <= 0:
        return 0.0
    age_days = max(0.0, (now_ms - event_time_ms) / 86_400_000.0)
    return float(0.5 ** (age_days / max(1e-9, half_life_days)))


def _fact_relevance_score(
    fact: SemanticFact, q_tokens: frozenset[str], q_low: str,
    now_ms: int | None = None,
) -> float:
    f_tokens = tokenize_query(f"{fact.subject} {fact.fact_text}")
    overlap = len(q_tokens & f_tokens)
    head = fact.subject.split("(")[0].strip().lower()
    subj_hit = 6.0 if (head and head in q_low) else 0.0
    lock_bonus = 5.0 if fact.is_locked else 0.0
    recency = fact_recency(fact.event_time_ms, now_ms or 0) * FACT_RECENCY_WEIGHT
    return overlap * 3.0 + subj_hit + lock_bonus + fact.confidence + recency


def select_relevant_facts(
    facts: tuple[SemanticFact, ...], query_text: str, limit: int = 28,
    now_ms: int | None = None,
) -> tuple[SemanticFact, ...]:
    """Rank semantic facts by relevance, lock status and event recency."""
    if len(facts) <= limit and now_ms is None:
        return facts
    q_tokens = tokenize_query(query_text)
    q_low = query_text.lower()
    scored = [
        (_fact_relevance_score(f, q_tokens, q_low, now_ms), idx, f)
        for idx, f in enumerate(facts)
    ]
    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return tuple(f for _, _, f in scored[:limit])


def extract_mentioned_uids(
    triggers: tuple[Percept, ...], facts: tuple[SemanticFact, ...]
) -> tuple[str, ...]:
    """Extract sender QQ IDs plus any member QQ IDs mentioned by name or number in triggers."""
    joined = " ".join(p.text for p in triggers)
    uids: list[str] = [p.sender_id for p in triggers if p.sender_id]
    uids.extend(QQ_NUM_RE.findall(joined))
    for f in facts:
        name_head = f.subject.split("(")[0].strip()
        if len(name_head) >= 2 and name_head in joined:
            uids.extend(QQ_NUM_RE.findall(f"{f.subject} {f.fact_text}"))
    return tuple(dict.fromkeys(uids))[:16]
