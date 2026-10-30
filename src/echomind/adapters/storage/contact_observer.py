"""Stage 40: adapter glue so message ingestion can record social contacts."""

from __future__ import annotations

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.domain.models import Percept
from echomind.mind.social_observer import observe_contact


async def observe_percept(
    db: SqliteDatabase, percept: Percept, operator_ids: tuple[str, ...] = ()
) -> None:
    """Create/refresh the sender's bond for one observed message."""
    repo = SqliteMemoryRepository(db)
    await observe_contact(repo, repo, percept, operator_ids=operator_ids)
