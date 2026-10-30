"""Stage 29 A3b: depth write-back and the legacy privilege reset."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.bond_depth_repo import SqliteBondDepthStore
from echomind.adapters.storage.bond_reset import reset_privileged_bonds
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.bond_scoring import attach_bond_depth


async def test_depth_is_written_back_to_the_bond(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "wb.db")
    await db.initialize()
    store = SqliteBondDepthStore(db)
    await store.ensure_schema()
    repo = __import__("echomind.adapters.storage.memory_repo", fromlist=["x"])
    mem = repo.SqliteMemoryRepository(db)
    bond = SocialBondProfile(chat_key="g", user_id="u1", user_name="u1",
                             affinity_score=90.0, trust_score=0.9)
    await mem.upsert_social_bond(bond)
    await store.upsert_stats(BondDepthStats(chat_key="g", user_id="u1", msgs=200, her_msgs=60,
                                            replies_to_them=40, responded_to_her=35, sessions=30))
    await attach_bond_depth(store, {"u1": bond})
    stored = await mem.get_social_bond("g", "u1")
    assert stored is not None and stored.bond_depth > 0


async def test_reset_clears_legacy_owner_sentinels(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "reset.db")
    await db.initialize()
    repo = __import__("echomind.adapters.storage.memory_repo", fromlist=["x"])
    mem = repo.SqliteMemoryRepository(db)
    legacy = SocialBondProfile(chat_key="g", user_id="o1", user_name="o1",
                               group_role="owner", affinity_score=9999.0, trust_score=1.0)
    await mem.upsert_social_bond(legacy)

    assert await reset_privileged_bonds(db, dry_run=True) == 1
    assert (await mem.get_social_bond("g", "o1")).affinity_score == 9999.0
    assert await reset_privileged_bonds(db) == 1
    cleaned = await mem.get_social_bond("g", "o1")
    assert cleaned is not None
    assert (cleaned.affinity_score, cleaned.trust_score) == (30.0, 0.75)
    assert cleaned.group_role == "member"
    assert await reset_privileged_bonds(db) == 0
