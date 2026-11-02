"""FTS5 is a lexical shadow index, not the live retriever."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_fts import FtsMemoryIndex
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_trigram_search_and_chat_filter(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "fts.db")
    await db.initialize()
    index = FtsMemoryIndex(db)
    await index.ensure_schema()
    await index.upsert(SemanticFact(
        fact_id=1, chat_key="group:1", subject="L", fact_text="L喜欢吃草莓蛋糕",
    ))
    await index.upsert(SemanticFact(
        fact_id=2, chat_key="group:2", subject="M", fact_text="M喜欢吃草莓蛋糕",
    ))
    assert await index.search("草莓蛋糕") == (1, 2)
    assert await index.search("草莓蛋糕", chat_key="group:1") == (1,)
    assert await index.search("不存在") == ()
