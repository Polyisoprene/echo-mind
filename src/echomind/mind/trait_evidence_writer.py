"""Extract the quote/context fields for a trait evidence row."""

from __future__ import annotations

import hashlib
from typing import Literal

from echomind.domain.models import PersonaTrait, TurnOutcome
from echomind.domain.trait_evidence import TraitEvidence
from echomind.domain.trait_evidence_ports import ITraitEvidenceStore
from echomind.domain.trait_memory_link import TraitMemoryLink
from echomind.domain.trait_memory_ports import ITraitMemoryLinkStore


def trait_quote(
    outcome: TurnOutcome,
) -> tuple[Literal["assistant", "user", "tool"], str] | None:
    for text in reversed(outcome.sent_texts):
        if text.strip():
            return "assistant", text.strip()
    if outcome.tools_used:
        return "tool", outcome.tools_used[-1]
    for percept in reversed(outcome.triggers):
        if percept.text.strip():
            return "user", percept.text.strip()
    return None


def evidence_context(outcome: TurnOutcome, now_ms: int) -> str:
    audience = sorted({p.sender_id for p in outcome.triggers if p.sender_id})
    event_ms = max(
        (p.timestamp_ms for p in outcome.triggers if p.timestamp_ms), default=now_ms
    )
    raw = f"{outcome.chat_key}|{','.join(audience)}|{event_ms // 86_400_000}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def record_evidence(
    outcome: TurnOutcome, trait: PersonaTrait,
    quote: tuple[Literal["assistant", "user", "tool"], str],
    evidence_store: ITraitEvidenceStore,
    trait_links: ITraitMemoryLinkStore | None, *,
    memory_ids: tuple[int, ...], now_ms: int,
) -> None:
    kind, text = quote
    await evidence_store.record_trait_evidence(TraitEvidence(
        trait_id=trait.trait_id, session_id=outcome.session_id,
        turn_id=outcome.session_id, quote=text, quote_kind=kind,
        polarity=1, context_hash=evidence_context(outcome, now_ms),
        memory_ids=memory_ids, created_ms=now_ms,
    ))
    await evidence_store.refresh_lifecycle(trait.trait_id)
    if trait_links is None:
        return
    for memory_id in memory_ids:
        await trait_links.link(TraitMemoryLink(
            trait_id=trait.trait_id, memory_kind="semantic",
            memory_id=memory_id, relation="supports", evidence_ms=now_ms,
        ))
