"""D4: the write path records who knows a fact from its source and owner."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.adapters.storage.disclosure_repo import SqliteDisclosureLog
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_fact_writes_knowledge_rows(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "know.db")
    repo = container.memory_repo
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="M 的工作", fact_text="M 在准备跳槽",
                     scope="person", source_person_id="L", owner_id="M", sensitivity="private")
    )
    fact = next(f for f in await repo.get_semantic_facts("group:1") if f.subject == "M 的工作")
    log = SqliteDisclosureLog(container.db)
    assert await log.who_knows("semantic", fact.fact_id) == (
        ("L", "told_to_me"), ("M", "knows"),
    )
