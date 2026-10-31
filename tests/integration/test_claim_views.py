"""Stage 39 S39-4a: the FACTS_V2 switch and claim-to-fact mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.adapters.storage.claim_views import claims_as_facts
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.mind.fact_shadow import ClaimView

NOW = 1_800_000_000_000


def _view(subject: str, value: str, *, predicate: str = "value", belief: float = 0.6,
          locked: bool = False, recorded: int = NOW) -> ClaimView:
    return ClaimView(subject=subject, value=value, predicate=predicate, belief=belief,
                     recorded_at_ms=recorded, locked=locked)


def test_claims_as_facts_dedupes_functional_and_mentions() -> None:
    views = [_view("群主", "A", belief=0.9), _view("群主", "B", belief=0.5),
             _view("L", "说1", predicate="mentioned", recorded=NOW),
             _view("L", "说2", predicate="mentioned", recorded=NOW - 1),
             _view("L", "说3", predicate="mentioned", recorded=NOW - 2)]
    facts = claims_as_facts(views)
    subjects = [f.subject for f in facts]
    assert subjects.count("群主") == 1 and subjects.count("L") == 2


async def test_facts_v2_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = SqliteDatabase(tmp_path / "v2.db")
    await db.initialize()
    monkeypatch.setenv("FACTS_V2", "on")
    with pytest.raises(RuntimeError, match="FACTS_V2"):
        SqliteMemoryRepository(db)
