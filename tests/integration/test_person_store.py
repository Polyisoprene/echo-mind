"""P1: person profiles persist as one relationship per person plus venue faces."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from echomind.adapters.storage.person_level_repo import load_bonds, load_stats
from echomind.adapters.storage.person_store import SqlitePersonStore
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.person_level import PersonProfile, build_profiles
from echomind.mind.person_level_service import PersonLevelService


@pytest.mark.asyncio
async def test_store_persists_person_and_venues(tmp_path: Path) -> None:
    db_path = tmp_path / "persons.db"
    container = await EchoMindContainer.create(db_path=db_path)
    repo = container.memory_repo
    await repo.upsert_social_bond(
        SocialBondProfile(chat_key="group:1", user_id="u", user_name="U",
                          affinity_score=54.5, trust_score=0.61, msg_count=680)
    )
    await repo.upsert_social_bond(
        SocialBondProfile(chat_key="private:u", user_id="u", user_name="U",
                          affinity_score=32.1, trust_score=0.78, msg_count=312)
    )
    await repo.upsert_social_bond(
        SocialBondProfile(chat_key="group:1", user_id="v", user_name="V",
                          affinity_score=20.0, trust_score=0.5, msg_count=10)
    )
    depth = container.bond_depth_store
    assert depth is not None
    await depth.upsert_stats(BondDepthStats(
        chat_key="group:1", user_id="u", msgs=368, sessions=49,
        responded_to_her=885, her_msgs=144, replies_to_them=144,
        impact_sum=2.76, impact_n=23,
    ))
    await depth.upsert_stats(BondDepthStats(
        chat_key="private:u", user_id="u", msgs=28, sessions=12,
        responded_to_her=14, her_msgs=23, replies_to_them=23,
        impact_sum=0.72, impact_n=6,
    ))
    await depth.upsert_stats(BondDepthStats(
        chat_key="group:1", user_id="v", msgs=10, sessions=2,
        responded_to_her=5, her_msgs=4, replies_to_them=4,
        impact_sum=0.1, impact_n=1,
    ))

    bonds, stats = await load_bonds(container.db), await load_stats(container.db)
    store = SqlitePersonStore(container.db)
    await store.save(build_profiles(bonds, stats), bonds)

    profiles = await store.load()
    assert set(profiles) == {"u", "v"}
    assert profiles["u"].trust == pytest.approx(0.663, abs=0.002)
    assert profiles["u"].depth_percentile == 100.0

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM person_bonds").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM bond_venues").fetchone()[0] == 3


@pytest.mark.asyncio
async def test_service_writes_through(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "svc.db")
    calls: list[int] = []

    async def persist(
        profiles: dict[str, PersonProfile], bonds: tuple[SocialBondProfile, ...]
    ) -> None:
        calls.append(len(profiles))

    service = PersonLevelService(
        lambda: load_bonds(container.db), lambda: load_stats(container.db), persist=persist
    )
    await service.profiles(1000)
    assert calls == [0]


@pytest.mark.asyncio
async def test_service_reads_persisted_profiles(tmp_path: Path) -> None:
    import time

    container = await EchoMindContainer.create(db_path=tmp_path / "read.db")
    store = SqlitePersonStore(container.db)
    await store.save(
        {"u": PersonProfile(person_id="u", trust=0.7, affinity=50.0,
                            depth_raw=2.0, depth_percentile=90.0)},
        (),
    )

    async def boom_bonds() -> tuple[SocialBondProfile, ...]:
        raise AssertionError("must not recompute when the snapshot is fresh")

    async def boom_stats() -> tuple[BondDepthStats, ...]:
        raise AssertionError("must not recompute when the snapshot is fresh")

    service = PersonLevelService(boom_bonds, boom_stats, load=store.load_with_ts)
    got = await service.profiles(int(time.time() * 1000))
    assert got["u"].trust == 0.7
    assert got["u"].depth_percentile == 90.0
