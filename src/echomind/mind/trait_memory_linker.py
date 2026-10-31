"""P3b: link trait evidence to memories only on exact source_quote equality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from echomind.domain.memory_quote_ports import IMemoryQuoteLookup
from echomind.domain.trait_evidence import TraitEvidence
from echomind.domain.trait_memory_link import TraitMemoryLink
from echomind.domain.trait_memory_ports import ITraitMemoryLinkStore


@dataclass(frozen=True)
class LinkResult:
    semantic: int = 0
    episodic: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.semantic + self.episodic


async def _link_ids(
    trait_id: int, kind: str, ids: tuple[int, ...], evidence_ms: int,
    store: ITraitMemoryLinkStore, *, dry_run: bool,
) -> int:
    for memory_id in ids:
        if not dry_run:
            await store.link(TraitMemoryLink(
                trait_id=trait_id, memory_kind=cast(Any, kind), memory_id=memory_id,
                relation="supports", evidence_ms=evidence_ms,
            ))
    return len(ids)


async def link_exact_quotes(
    trait_id: int, chat_key: str, evidence: tuple[TraitEvidence, ...],
    lookup: IMemoryQuoteLookup, store: ITraitMemoryLinkStore, *, dry_run: bool = False,
) -> LinkResult:
    """Create only exact-quote links; never fuzzy-match or infer a threshold."""
    semantic = episodic = skipped = 0
    for item in evidence:
        if item.polarity <= 0:
            continue
        sem_ids = await lookup.semantic_ids(chat_key, item.quote)
        epi_ids = await lookup.episodic_ids(chat_key, item.quote)
        if not sem_ids and not epi_ids:
            skipped += 1
            continue
        semantic += await _link_ids(
            trait_id, "semantic", sem_ids, item.created_ms, store, dry_run=dry_run
        )
        episodic += await _link_ids(
            trait_id, "episodic", epi_ids, item.created_ms, store, dry_run=dry_run
        )
    return LinkResult(semantic, episodic, skipped)
