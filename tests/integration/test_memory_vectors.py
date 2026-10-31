"""D15: vector persistence round-trips per memory id."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.adapters.storage.memory_vector_repo import SqliteMemoryVectorStore
from echomind.core.bootstrap import EchoMindContainer


@pytest.mark.asyncio
async def test_vector_roundtrip(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "vec.db")
    store = SqliteMemoryVectorStore(container.db)
    await store.upsert(memory_kind="semantic", memory_id=1, model="m",
                       vector=(0.1, 0.2, 0.3))
    await store.upsert(memory_kind="semantic", memory_id=2, model="m",
                       vector=(0.4, 0.5, 0.6))
    got = await store.get("semantic", (1, 2))
    assert got[1] == pytest.approx((0.1, 0.2, 0.3))
    assert got[2] == pytest.approx((0.4, 0.5, 0.6))
    assert set(await store.load_all("semantic")) == {1, 2}
