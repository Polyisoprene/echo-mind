"""Live cross-session merge is opt-in and excludes private/secret facts."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_live_merge_is_on_by_default_and_can_be_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "live.db")
    repo = container.memory_repo
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="group:1", subject="群公告", fact_text="周五发图",
        scope="venue", sensitivity="public",
    ))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="private:1", subject="私聊约定", fact_text="别在群里说",
        scope="venue", sensitivity="group",
    ))
    monkeypatch.delenv("CROSS_SESSION_MEMORY", raising=False)
    subjects = {f.subject for f in await repo.get_semantic_facts("group:2")}
    assert "群公告" in subjects
    assert "私聊约定" not in subjects
    monkeypatch.setenv("CROSS_SESSION_MEMORY", "off")
    assert "群公告" not in {f.subject for f in await repo.get_semantic_facts("group:2")}
