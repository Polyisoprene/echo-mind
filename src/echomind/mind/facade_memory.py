"""Memory recall/reinforcement and dialogue consolidation used by the facade."""

from __future__ import annotations

import time

from echomind.domain.models import Percept
from echomind.domain.ports import ILlmGateway, IMemoryReader, IMemoryWriter, IWorkingStateStore
from echomind.mind.ebbinghaus import recall_episodic_memories
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


__all__ = ["consolidate_dialogue", "recall_and_reinforce"]
