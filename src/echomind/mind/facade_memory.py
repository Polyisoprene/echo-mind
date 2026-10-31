"""Memory recall, dialogue consolidation and the frame-level disclosure gate."""

from __future__ import annotations

import time

from echomind.domain.models import Percept, SemanticFact
from echomind.domain.ports import (
    IDisclosureLog,
    ILlmGateway,
    IMemoryReader,
    IMemoryWriter,
    IWorkingStateStore,
)
from echomind.mind.disclosure import gate_episode, gate_fact
from echomind.mind.ebbinghaus import extract_mentioned_uids, recall_episodic_memories
from echomind.mind.memory_consolidator import run_hippocampal_batch_consolidation
from echomind.mind.recall_types import RecalledMemoryItem


async def recall_and_reinforce(
    reader: IMemoryReader,
    writer: IMemoryWriter,
    *,
    chat_key: str,
    triggers: tuple[Percept, ...],
    uids: tuple[str, ...],
    now_ms: int,
    dry_run: bool = False,
) -> tuple[RecalledMemoryItem, ...]:
    cards = await reader.get_episodic_cards(chat_key)
    recalled = recall_episodic_memories(cards, " ".join(p.text for p in triggers), uids, now_ms)
    if not dry_run:
        for item in recalled:
            await writer.reinforce_episodic_card(item.card.card_id, now_ms)
    return recalled


async def consolidate_dialogue(
    reader: IMemoryReader,
    writer: IMemoryWriter,
    llm: ILlmGateway,
    working: IWorkingStateStore,
    *,
    chat_key: str,
    transcript_lines: tuple[str, ...],
    role_text: str = "",
) -> int:
    return await run_hippocampal_batch_consolidation(
        chat_key, reader, writer, llm, transcript_lines,
        now_ms=int(time.time() * 1000), working_store=working, role_text=role_text,
    )


async def load_facts(
    reader: IMemoryReader, chat_key: str, triggers: tuple[Percept, ...]
) -> tuple[tuple[SemanticFact, ...], tuple[str, ...]]:
    facts = await reader.get_semantic_facts(chat_key)
    uids = extract_mentioned_uids(triggers, facts)
    facts = await reader.get_semantic_facts(chat_key, person_ids=uids)
    return facts, uids


def audience_of(uids: tuple[str, ...], triggers: tuple[Percept, ...]) -> frozenset[str]:
    sender = triggers[-1].sender_id if triggers else ""
    return frozenset((*uids, sender)) - {""}


async def _gate_facts(
    facts: tuple[SemanticFact, ...],
    audience: frozenset[str],
    venue: str,
    log: IDisclosureLog | None,
) -> tuple[SemanticFact, ...]:
    kept: list[SemanticFact] = []
    for fact in facts:
        decision = gate_fact(fact, audience, venue)
        if decision.allowed:
            kept.append(fact)
            continue
        if log is not None:
            await log.log_disclosure(
                memory_kind="semantic", memory_id=fact.fact_id, venue=venue,
                audience=tuple(sorted(audience)), action="keep", reason=decision.reason,
            )
    return tuple(kept)


async def _gate_recalled(
    recalled: tuple[RecalledMemoryItem, ...],
    audience: frozenset[str],
    venue: str,
    log: IDisclosureLog | None,
) -> tuple[RecalledMemoryItem, ...]:
    kept: list[RecalledMemoryItem] = []
    for item in recalled:
        decision = gate_episode(item.card, audience, venue)
        if decision.allowed:
            kept.append(item)
            continue
        if log is not None:
            await log.log_disclosure(
                memory_kind="episodic", memory_id=item.card.card_id, venue=venue,
                audience=tuple(sorted(audience)), action="keep", reason=decision.reason,
            )
    return tuple(kept)


async def gate_frame(
    facts: tuple[SemanticFact, ...],
    recalled: tuple[RecalledMemoryItem, ...],
    audience: frozenset[str],
    venue: str,
    log: IDisclosureLog | None,
) -> tuple[tuple[SemanticFact, ...], tuple[RecalledMemoryItem, ...]]:
    """Apply the hard gate to what is about to enter the prompt, logging refusals."""
    gated_facts = await _gate_facts(facts, audience, venue, log)
    gated_recalled = await _gate_recalled(recalled, audience, venue, log)
    return gated_facts, gated_recalled


__all__ = [
    "audience_of", "consolidate_dialogue", "gate_frame", "load_facts",
    "recall_and_reinforce",
]
