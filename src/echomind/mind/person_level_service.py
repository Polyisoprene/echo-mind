"""Cache one person-level profile set, rebuilt from the venue bonds and depth stats."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.mind.person_level import PersonProfile, build_profiles

BondsLoader = Callable[[], Awaitable[tuple[SocialBondProfile, ...]]]
StatsLoader = Callable[[], Awaitable[tuple[BondDepthStats, ...]]]
Persist = Callable[[dict[str, PersonProfile], tuple[SocialBondProfile, ...]], Awaitable[None]]
Load = Callable[[], Awaitable[tuple[dict[str, PersonProfile], int]]]


class PersonLevelService:
    """Loads all venue rows, collapses them per person, and caches for a short TTL."""

    def __init__(
        self,
        bonds: BondsLoader,
        stats: StatsLoader,
        ttl_ms: int = 60_000,
        persist: Persist | None = None,
        load: Load | None = None,
    ) -> None:
        self._bonds = bonds
        self._stats = stats
        self._ttl_ms = ttl_ms
        self._persist = persist
        self._load = load
        self._cache: dict[str, PersonProfile] = {}
        self._loaded_ms = -1

    async def profiles(self, now_ms: int) -> dict[str, PersonProfile]:
        if self._cache and now_ms - self._loaded_ms < self._ttl_ms:
            return self._cache
        if self._load is not None:
            cached, ts = await self._load()
            if cached and now_ms - ts < self._ttl_ms:
                self._cache = cached
                self._loaded_ms = ts
                return cached
        bonds = await self._bonds()
        self._cache = build_profiles(bonds, await self._stats())
        self._loaded_ms = now_ms
        if self._persist is not None:
            await self._persist(self._cache, bonds)
        return self._cache

    def invalidate(self) -> None:
        self._cache = {}
        self._loaded_ms = -1


__all__ = ["PersonLevelService"]
