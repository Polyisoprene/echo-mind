"""Persist consolidation-produced relations without widening IMemoryWriter."""

from __future__ import annotations

from typing import Any

from echomind.domain.relation import MemoryRelation


async def persist_relations(
    writer: Any, relations: tuple[MemoryRelation, ...]
) -> int:
    upsert = getattr(writer, "upsert_relation", None)
    if upsert is None:
        return 0
    for relation in relations:
        await upsert(relation)
    return len(relations)


__all__ = ["persist_relations"]
