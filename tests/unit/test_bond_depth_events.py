"""Stage 29 A2b: persisted interaction counters -> six features -> earned depth."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.bond_depth_repo import SqliteBondDepthStore
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.bond_stats import BondDepthStats
from echomind.mind.bond_features import depth_from_stats, features_from_stats


async def _store(tmp_path: Path) -> SqliteBondDepthStore:
    db = SqliteDatabase(tmp_path / "bond.db")
    await db.initialize()
    store = SqliteBondDepthStore(db)
    await store.ensure_schema()
    return store


async def test_stats_roundtrip_and_impact_accumulation(tmp_path: Path) -> None:
    store = await _store(tmp_path)
    await store.upsert_stats(
        BondDepthStats(chat_key="group:A", user_id="u1", msgs=120, her_msgs=40,
                       replies_to_them=30, responded_to_her=18, sessions=5)
    )
    await store.add_impact("group:A", "u1", 12.5)
    await store.add_impact("group:A", "u1", 7.5, betray=True)

    stats = await store.get_stats("group:A", "u1")
    assert stats is not None
    assert stats.msgs == 120 and stats.her_msgs == 40
    assert stats.impact_n == 2
    assert abs(stats.impact_sum - 20.0) < 1e-6
    assert stats.betrayals == 1

    await store.upsert_stats(
        BondDepthStats(chat_key="group:A", user_id="u2", msgs=400)
    )
    top = await store.top_stats(limit=5)
    assert [s.user_id for s in top] == ["u2", "u1"]


async def test_features_and_depth_reflect_reciprocated_history() -> None:
    friend = BondDepthStats(
        chat_key="g", user_id="friend", msgs=180, her_msgs=60, replies_to_them=48,
        responded_to_her=36, sessions=6, impact_sum=30.0, impact_n=60,
    )
    praiser = BondDepthStats(
        chat_key="g", user_id="praiser", msgs=400, her_msgs=60, replies_to_them=6,
        responded_to_her=3, sessions=1, impact_sum=6.0, impact_n=60,
    )
    stranger = BondDepthStats(chat_key="g", user_id="nobody")

    f = features_from_stats(friend)
    assert f.responsivity > 0.5 and f.reciprocity > 0.35 and f.diversity > 0.4
    assert depth_from_stats(friend) > depth_from_stats(praiser) > depth_from_stats(stranger)
    assert depth_from_stats(stranger) <= 3.0
