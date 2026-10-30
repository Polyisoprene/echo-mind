"""Stage 40: backfill historical speakers into social bonds (idempotent, no score changes)."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.contact_backfill import backfill_contacts
from echomind.adapters.storage.database import SqliteDatabase


async def _seed(db: SqliteDatabase) -> None:
    async with db.connect() as conn:
        for i, (uid, name) in enumerate([("1", "A"), ("1", "A"), ("2", "B")]):
            await conn.execute(
                "INSERT INTO chat_messages (chat_key, mid, ts, sender_id, sender_name, "
                "is_self, text, media_json) VALUES (?,?,?,?,?,0,'hi','[]')",
                ("group:1", f"m{i}", 1000 + i, uid, name),
            )
        await conn.commit()


async def test_backfill_creates_missing_bonds(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "cb.db")
    await db.initialize()
    await _seed(db)
    report = await backfill_contacts(db)
    assert report["senders"] == 2 and report["created"] == 2


async def test_backfill_is_idempotent_and_counts_messages(tmp_path: Path) -> None:
    from echomind.adapters.storage.memory_repo import SqliteMemoryRepository

    db = SqliteDatabase(tmp_path / "cb2.db")
    await db.initialize()
    await _seed(db)
    await backfill_contacts(db)
    await backfill_contacts(db)
    repo = SqliteMemoryRepository(db)
    a = await repo.get_social_bond("group:1", "1")
    b = await repo.get_social_bond("group:1", "2")
    assert a is not None and b is not None
    assert a.msg_count == 2 and b.msg_count == 1
    assert a.affinity_score == 30.0


async def test_backfill_never_lowers_existing_counts(tmp_path: Path) -> None:
    from echomind.adapters.storage.memory_repo import SqliteMemoryRepository

    db = SqliteDatabase(tmp_path / "cb3.db")
    await db.initialize()
    await _seed(db)
    repo = SqliteMemoryRepository(db)
    await backfill_contacts(db)
    bond = await repo.get_social_bond("group:1", "1")
    assert bond is not None
    await repo.upsert_social_bond(bond.model_copy(update={"msg_count": 99}))
    await backfill_contacts(db)
    again = await repo.get_social_bond("group:1", "1")
    assert again is not None and again.msg_count == 99
