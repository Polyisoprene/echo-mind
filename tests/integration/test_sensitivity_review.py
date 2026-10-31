"""D7: a cue-raised sensitivity can be reviewed and corrected with an audit row."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from echomind.adapters.storage.sensitivity_repo import SqliteSensitivityReviewer
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SemanticFact


@pytest.mark.asyncio
async def test_review_downgrades_and_records(tmp_path: Path) -> None:
    db_path = tmp_path / "review.db"
    container = await EchoMindContainer.create(db_path=db_path)
    repo = container.memory_repo
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="误报", fact_text="这是秘密吗",
                     sensitivity="secret")
    )
    fact_id = sqlite3.connect(db_path).execute(
        "SELECT id FROM semantic_facts WHERE subject='误报'"
    ).fetchone()[0]
    reviewer = SqliteSensitivityReviewer(container.db)
    pending = await reviewer.list_non_group()
    assert any(row["id"] == fact_id for row in pending)

    previous = await reviewer.apply(
        memory_kind="semantic", memory_id=fact_id, to_sensitivity="group",
        reviewer="operator", reason="引用，不是秘密",
    )
    assert previous == "secret"
    updated = next(f for f in await repo.get_semantic_facts("group:1") if f.subject == "误报")
    assert updated.sensitivity == "group"

    row = sqlite3.connect(db_path).execute(
        "SELECT from_sensitivity, to_sensitivity, reviewer FROM sensitivity_reviews"
    ).fetchone()
    assert row == ("secret", "group", "operator")
