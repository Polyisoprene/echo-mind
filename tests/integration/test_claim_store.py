# mypy: disable-error-code="import-untyped"
"""Stage 39 S39-0: claim/evidence store skeleton (red until S39-1 lands)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from echomind.adapters.storage.database import SqliteDatabase


async def test_claim_tables_exist_after_initialize(tmp_path: Path) -> None:
    db_path = tmp_path / "claims.db"
    await SqliteDatabase(db_path).initialize()
    con = sqlite3.connect(str(db_path))
    names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    assert {"claims", "claim_evidence", "fact_reviews"} <= names


async def test_claim_evidence_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "claims2.db"
    await SqliteDatabase(db_path).initialize()
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(claim_evidence)")}
    assert {"claim_id", "source_type", "weight", "observed_at_ms"} <= cols


@pytest.mark.xfail(strict=True, reason="S39-1: claim store not implemented yet")
async def test_upsert_and_believe(tmp_path: Path) -> None:
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    store = SqliteClaimStore(SqliteDatabase(tmp_path / "c.db"))
    await store.ensure_schema()
    claim_id = await store.assert_claim(
        "group:1", "本群群主", "value", "馍馍", source_type="system", source_id="sys"
    )
    assert await store.claim_belief(claim_id) > 0.5


@pytest.mark.xfail(strict=True, reason="S39-1: claim store not implemented yet")
async def test_conflict_opens_review(tmp_path: Path) -> None:
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    store = SqliteClaimStore(SqliteDatabase(tmp_path / "c2.db"))
    await store.ensure_schema()
    await store.assert_claim("group:1", "群主", "value", "A", source_type="system", source_id="s")
    for i in range(3):
        await store.assert_claim(
            "group:1", "群主", "value", "B", source_type="peer", source_id=f"u{i}"
        )
    assert await store.open_reviews("group:1") >= 1


@pytest.mark.xfail(strict=True, reason="S39-1: retraction not implemented yet")
async def test_retract_keeps_history(tmp_path: Path) -> None:
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    store = SqliteClaimStore(SqliteDatabase(tmp_path / "c3.db"))
    await store.ensure_schema()
    claim_id = await store.assert_claim(
        "group:1", "回音的主人", "value", "L", source_type="system", source_id="s"
    )
    await store.retract(claim_id, reason="D2: no emotional owner")
    assert await store.claim_status(claim_id) == "retracted"


@pytest.mark.xfail(strict=True, reason="S39-1: bitemporal lookup not implemented yet")
async def test_as_of_lookup(tmp_path: Path) -> None:
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    store = SqliteClaimStore(SqliteDatabase(tmp_path / "c4.db"))
    await store.ensure_schema()
    await store.assert_claim(
        "group:1", "群主", "value", "A", source_type="system", source_id="s",
        valid_from_ms=0, valid_to_ms=1_000,
    )
    await store.assert_claim(
        "group:1", "群主", "value", "B", source_type="system", source_id="s",
        valid_from_ms=1_000, valid_to_ms=2_000,
    )
    assert await store.current_value("group:1", "群主", as_of_ms=500) == "A"
    assert await store.current_value("group:1", "群主", as_of_ms=1_500) == "B"
