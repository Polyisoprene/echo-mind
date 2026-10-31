"""P0.2: the store layer returns one person, even with two venue rows."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.adapters.storage.person_level_repo import load_bonds, load_stats
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.person_level_service import PersonLevelService


@pytest.mark.asyncio
async def test_profiles_collapse_venues_and_cache(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "person.db")
    repo = container.memory_repo
    await repo.upsert_social_bond(
        SocialBondProfile(
            chat_key="group:1", user_id="u", user_name="u", affinity_score=54.5,
            trust_score=0.61, msg_count=680, bond_depth=71.0,
        )
    )
    await repo.upsert_social_bond(
        SocialBondProfile(
            chat_key="private:u", user_id="u", user_name="u", affinity_score=32.1,
            trust_score=0.78, msg_count=312, bond_depth=50.7,
        )
    )
    depth = container.bond_depth_store
    assert depth is not None
    await depth.upsert_stats(
        BondDepthStats(chat_key="group:1", user_id="u", msgs=368, sessions=49,
                       responded_to_her=885, her_msgs=144, replies_to_them=144,
                       impact_sum=2.76, impact_n=23)
    )
    await depth.upsert_stats(
        BondDepthStats(chat_key="private:u", user_id="u", msgs=28, sessions=12,
                       responded_to_her=14, her_msgs=23, replies_to_them=23,
                       impact_sum=0.72, impact_n=6)
    )
    await repo.upsert_social_bond(
        SocialBondProfile(
            chat_key="group:1", user_id="v", user_name="v", affinity_score=20.0,
            trust_score=0.5, msg_count=10, bond_depth=0.0,
        )
    )
    await depth.upsert_stats(
        BondDepthStats(chat_key="group:1", user_id="v", msgs=10, sessions=2,
                       responded_to_her=5, her_msgs=4, replies_to_them=4,
                       impact_sum=0.1, impact_n=1)
    )

    service = PersonLevelService(lambda: load_bonds(container.db), lambda: load_stats(container.db))
    profiles = await service.profiles(1000)
    assert set(profiles) == {"u", "v"}
    assert profiles["u"].trust == pytest.approx(0.663, abs=0.002)
    assert profiles["u"].depth_percentile == 100.0
    assert profiles["v"].depth_percentile == 0.0

    assert await service.profiles(2000) is profiles, "within TTL the cache is returned"
    service.invalidate()
    assert await service.profiles(3000) is not profiles
