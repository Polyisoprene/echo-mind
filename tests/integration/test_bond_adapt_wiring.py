"""Stage 29 B2/B3/B4: group calibration, shrinkage and drift detection in the scoring path."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.bond_depth_repo import SqliteBondDepthStore
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.bond_scoring import attach_bond_depth, observe_group_drift


def _stats(uid: str, msgs: int, replies: int, resp: int, sessions: int) -> BondDepthStats:
    return BondDepthStats(
        chat_key="g", user_id=uid, msgs=msgs, her_msgs=40,
        replies_to_them=replies, responded_to_her=resp, sessions=sessions,
    )


async def test_small_group_keeps_identity_calibration(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "a.db")
    await db.initialize()
    store = SqliteBondDepthStore(db)
    await store.ensure_schema()
    await store.upsert_stats(_stats("u1", 40, 10, 12, 6))
    bonds = {"u1": SocialBondProfile(chat_key="g", user_id="u1", user_name="u1",
                                     affinity_score=70.0, trust_score=0.85)}
    out = await attach_bond_depth(store, bonds)
    assert out["u1"].bond_depth > 0


async def test_group_calibration_spreads_a_clustered_group(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "b.db")
    await db.initialize()
    store = SqliteBondDepthStore(db)
    await store.ensure_schema()
    for i in range(12):
        await store.upsert_stats(_stats(f"u{i}", 120 + i * 5, 30 + i, 25 + i, 30 + i))
    bonds = {
        f"u{i}": SocialBondProfile(chat_key="g", user_id=f"u{i}", user_name=f"u{i}",
                                   affinity_score=80.0, trust_score=0.9)
        for i in range(12)
    }
    out = await attach_bond_depth(store, bonds)
    depths = [out[f"u{i}"].bond_depth for i in range(12)]
    assert max(depths) - min(depths) > 3.0, "ranks must still separate similar people"
    assert all(0.0 <= d <= 100.0 for d in depths)


def test_drift_detector_flags_a_level_shift() -> None:
    quiet = [observe_group_drift("g-drift", 50.0 + (i % 3) * 0.1) for i in range(40)]
    assert not any(quiet)
    shifted = [observe_group_drift("g-drift", 80.0) for _ in range(60)]
    assert any(shifted), "a sustained level shift must raise the drift alarm"
