"""Stage 30 S30-5: trait provenance, category caps and category-scoped decay."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import PersonaTrait


async def _store(tmp_path: Path) -> tuple[SqliteDatabase, SqliteWorkingStateStore]:
    db = SqliteDatabase(tmp_path / "t.db")
    await db.initialize()
    return db, SqliteWorkingStateStore(db)


async def test_traits_record_provenance(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    await store.sync_persona_traits(
        PersonaTrait(category="habit", trait_text="喜欢先查梗再接话", strength=6),
        chat_key="group:1", source="turn:s1",
    )
    async with db.connect() as conn:
        cursor = await conn.execute(
            "SELECT chat_key, source FROM persona_traits WHERE trait_text='喜欢先查梗再接话'"
        )
        row = await cursor.fetchone()
    assert row == ("group:1", "turn:s1")


async def test_category_caps_are_enforced(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    for i in range(12):
        await store.sync_persona_traits(
            PersonaTrait(category="habit", trait_text=f"习惯{i}", strength=5 + i % 3),
            chat_key="g", source="turn:x",
        )
    async with db.connect() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM persona_traits WHERE category='habit'")
        row = await cursor.fetchone()
    assert row is not None and row[0] <= 8


async def test_negative_shift_only_touches_taboo_and_temperament(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    await store.sync_persona_traits(PersonaTrait(category="habit", trait_text="怕冷", strength=6))
    await store.sync_persona_traits(
        PersonaTrait(category="taboo", trait_text="讨厌被使唤", strength=6)
    )
    await store.sync_persona_traits(
        strength_delta=-2, decay_categories=("taboo", "temperament")
    )
    async with db.connect() as conn:
        cursor = await conn.execute(
            "SELECT category, strength FROM persona_traits ORDER BY category"
        )
        rows: dict[str, int] = {row[0]: row[1] for row in await cursor.fetchall()}
    assert rows["habit"] == 6, "positive-category habit must not decay"
    assert rows["taboo"] == 4, "taboo must decay when targeted"
