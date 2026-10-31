"""Optimistic retry loop for working-state mutations (D16)."""

from __future__ import annotations

from collections.abc import Callable

from echomind.domain.errors import WorkingStateConflict
from echomind.domain.models import WorkingSnapshot
from echomind.domain.ports import IWorkingStateStore

Mutator = Callable[[WorkingSnapshot], WorkingSnapshot]


async def mutate_working_state(
    store: IWorkingStateStore, scope_key: str, mutator: Mutator, retries: int = 3
) -> WorkingSnapshot:
    """Apply a pure mutator to the latest snapshot, retrying on a version conflict."""
    for _ in range(retries):
        current = await store.load_working_state(scope_key)
        updated = mutator(current)
        if updated == current:
            return current
        try:
            await store.save_working_state(updated)
            return updated
        except WorkingStateConflict:
            continue
    raise WorkingStateConflict(scope_key)


__all__ = ["mutate_working_state"]
