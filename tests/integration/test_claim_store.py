# mypy: disable-error-code="import-untyped"
"""Stage 39: claim/evidence store (belief, conflict review, retraction, as-of)."""

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


async def test_upsert_and_believe(tmp_path: Path) -> None:
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    store = SqliteClaimStore(SqliteDatabase(tmp_path / "c.db"))
    await store.ensure_schema()
    claim_id = await store.assert_claim(
        "group:1", "本群群主", "value", "馍馍", source_type="system", source_id="sys"
    )
    assert await store.claim_belief(claim_id) > 0.5


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


async def test_retract_keeps_history(tmp_path: Path) -> None:
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    store = SqliteClaimStore(SqliteDatabase(tmp_path / "c3.db"))
    await store.ensure_schema()
    claim_id = await store.assert_claim(
        "group:1", "回音的主人", "value", "L", source_type="system", source_id="s"
    )
    await store.retract(claim_id, reason="D2: no emotional owner")
    assert await store.claim_status(claim_id) == "retracted"


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


async def test_dual_write_mirrors_fact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
    from echomind.domain.models import SemanticFact

    db = SqliteDatabase(tmp_path / "dw.db")
    await db.initialize()
    repo = SqliteMemoryRepository(db)
    fact = SemanticFact(
        chat_key="group:1", subject="本群群主", fact_text="群主是 A", confidence=0.9,
        is_locked=True, source="owner",
    )
    monkeypatch.setenv("FACTS_V2_WRITE", "on")
    ok, _ = await repo.upsert_semantic_fact(fact)
    assert ok
    claim_id = await _first_claim_id(tmp_path / "dw.db")
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    assert await SqliteClaimStore(db).claim_belief(claim_id) > 0.5


async def test_dual_write_off_by_default(tmp_path: Path) -> None:
    from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
    from echomind.domain.models import SemanticFact

    db = SqliteDatabase(tmp_path / "nw.db")
    await db.initialize()
    repo = SqliteMemoryRepository(db)
    await repo.upsert_semantic_fact(
        SemanticFact(chat_key="group:1", subject="s", fact_text="v", confidence=0.9)
    )
    assert await _claim_count(tmp_path / "nw.db") == 0


async def _claim_count(path: Path) -> int:
    import sqlite3

    con = sqlite3.connect(str(path))
    return int(con.execute("select count(*) from claims").fetchone()[0])


async def _first_claim_id(path: Path) -> int:
    import sqlite3

    con = sqlite3.connect(str(path))
    return int(con.execute("select id from claims order by id limit 1").fetchone()[0])


async def test_single_value_slot_supersedes_old_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from echomind.adapters.storage.claim_repo import SqliteClaimStore

    monkeypatch.setenv("CLAIM_SLOT_SUPERSEDE", "on")
    monkeypatch.setenv("CLAIM_SLOT_INFER", "on")
    db_path = tmp_path / "slot.db"
    store = SqliteClaimStore(SqliteDatabase(db_path))
    await store.ensure_schema()
    old = await store.assert_claim(
        "group:1", "L", "value", "QQ号是 123456789",
        source_type="system", source_id="s1", slot_key="person.qq",
    )
    new = await store.assert_claim(
        "group:1", "L", "value", "QQ号是 987654321",
        source_type="system", source_id="s2", slot_key="person.qq",
    )
    con = sqlite3.connect(str(db_path))
    rows = dict(con.execute("select id,status from claims where subject='L'").fetchall())
    assert rows[old] == "superseded"
    assert rows[new] == "asserted"
    assert con.execute("select superseded_by from claims where id=?", (old,)).fetchone()[0] == new
