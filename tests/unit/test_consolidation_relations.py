"""Consolidation parses and persists typed relations."""

from __future__ import annotations

import json

import pytest

from echomind.domain.relation import MemoryRelation
from echomind.mind.hippocampus import parse_consolidation_json
from echomind.mind.relation_persist import persist_relations


def test_consolidation_parses_relations_and_skips_invalid() -> None:
    raw = json.dumps({"relations": [
        {"subject": "A", "predicate": "friend", "object": "B", "confidence": 0.9},
        {"subject": "A", "predicate": "unknown", "object": "B"},
    ]})
    parsed = parse_consolidation_json("g", raw, 1)
    assert [(r.subject_id, r.predicate, r.object_id) for r in parsed.relations] == [
        ("A", "friend", "B")
    ]


@pytest.mark.asyncio
async def test_persist_relations_uses_writer_hook() -> None:
    class Writer:
        def __init__(self) -> None:
            self.items: list[MemoryRelation] = []

        async def upsert_relation(self, relation: MemoryRelation) -> None:
            self.items.append(relation)

    writer = Writer()
    relation = MemoryRelation(subject_id="A", predicate="friend", object_id="B")
    assert await persist_relations(writer, (relation,)) == 1
    assert writer.items == [relation]
