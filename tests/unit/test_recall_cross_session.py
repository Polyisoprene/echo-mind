"""RecallMemoryTool can opt into cross-session public/group facts."""

from __future__ import annotations

from typing import Any, cast

from echomind.domain.models import SemanticFact
from echomind.domain.ports import IMemoryReader
from echomind.tools.member_memory import RecallMemoryTool


class _Reader:
    async def get_semantic_facts(self, chat_key: str) -> tuple[SemanticFact, ...]:
        return (SemanticFact(chat_key=chat_key, subject="本地", fact_text="本群事实"),)

    async def get_episodic_cards(self, chat_key: str) -> tuple[Any, ...]:
        return ()

    async def get_cross_session_facts(self, chat_key: str) -> tuple[SemanticFact, ...]:
        return (SemanticFact(chat_key="group:2", subject="跨群", fact_text="公开事实"),)


async def test_opt_in_cross_session_recall() -> None:
    tool = RecallMemoryTool(cast(IMemoryReader, _Reader()))
    default = await tool.execute("group:1", {"query": "公开"})
    assert "公开事实" not in default
    cross = await tool.execute(
        "group:1", {"query": "公开", "include_cross_session": True},
    )
    assert "公开事实" in cross
