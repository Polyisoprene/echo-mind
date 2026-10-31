"""D16: versioned writes reject stale snapshots and mutate retries on conflict."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.errors import WorkingStateConflict
from echomind.domain.models import WorkingSnapshot
from echomind.mind.working_update import mutate_working_state


def _bump(snapshot: WorkingSnapshot) -> WorkingSnapshot:
    return snapshot.model_copy(update={"inner_thought": str(int(snapshot.inner_thought) + 1)})


@pytest.mark.asyncio
async def test_stale_snapshot_is_rejected(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "v.db")
    store = container.working_store
    await store.save_working_state(WorkingSnapshot(scope_key="global", inner_thought="0"))
    first = await store.load_working_state("global")
    second = await store.load_working_state("global")
    assert first.revision > 0
    await store.save_working_state(_bump(first))
    with pytest.raises(WorkingStateConflict):
        await store.save_working_state(_bump(second))


@pytest.mark.asyncio
async def test_concurrent_mutations_retry_without_losing(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "r.db")
    store = container.working_store
    await store.save_working_state(WorkingSnapshot(scope_key="global", inner_thought="0"))
    await asyncio.gather(
        mutate_working_state(store, "global", _bump),
        mutate_working_state(store, "global", _bump),
    )
    final = await store.load_working_state("global")
    assert final.inner_thought == "2"
