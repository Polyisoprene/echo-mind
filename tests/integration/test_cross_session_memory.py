"""Cross-session read path is opt-in and respects source/audience."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_cross_session_reads_group_public_but_not_private_source(
    tmp_path: Path,
) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "cross.db")
    repo = container.memory_repo
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="group:1", subject="群公告", fact_text="周五发图",
        scope="venue", sensitivity="group",
    ))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="private:1", subject="私聊约定", fact_text="别在群里说",
        scope="venue", sensitivity="group",
    ))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="group:1", subject="秘密", fact_text="不能外传",
        scope="venue", sensitivity="secret",
    ))
    subjects = {fact.subject for fact in await repo.get_cross_session_facts("group:2")}
    assert "群公告" in subjects
    assert "私聊约定" not in subjects
    assert "秘密" not in subjects
