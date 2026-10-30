"""Stage 29 wiring: earned depth reaches the social bond and lifts w_care."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.bond_depth_repo import SqliteBondDepthStore
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.bond_scoring import attach_bond_depth
from echomind.mind.drives import compute_care_weight


async def test_attach_bond_depth_fills_and_boosts_care(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "wire.db")
    await db.initialize()
    store = SqliteBondDepthStore(db)
    await store.ensure_schema()
    await store.upsert_stats(
        BondDepthStats(chat_key="g", user_id="u1", msgs=200, her_msgs=60, replies_to_them=45,
                       responded_to_her=40, sessions=35, impact_sum=30.0, impact_n=60)
    )
    bonds = {"u1": SocialBondProfile(chat_key="g", user_id="u1", user_name="u1",
                                     affinity_score=81.66, trust_score=0.85)}
    filled = await attach_bond_depth(store, bonds)
    depth = filled["u1"].bond_depth
    assert depth > 30.0, f"depth must be filled from stats, got {depth}"

    plain = compute_care_weight("u1", "", bonds["u1"])
    earned = compute_care_weight("u1", "", filled["u1"])
    assert earned > plain, f"earned depth must raise care ({plain} -> {earned})"
    assert earned <= 0.97


async def test_container_exposes_bond_store_and_keeps_care_backward_compatible(
    tmp_path: Path,
) -> None:
    container = await EchoMindContainer.create(
        db_path=tmp_path / "c.db", owner_qq="10001001", default_chat_key="group:10002002"
    )
    assert container.bond_depth_store is not None
    bond = SocialBondProfile(chat_key="g", user_id="u2", user_name="u2",
                             affinity_score=81.66, trust_score=0.85)
    assert compute_care_weight("u2", "", bond) == 0.53, "zero depth must match the pre-29 formula"
