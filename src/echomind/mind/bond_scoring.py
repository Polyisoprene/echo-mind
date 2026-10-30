"""Attach earned bond depth to social bonds before the mind layers read them."""

from __future__ import annotations

from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.models import SocialBondProfile
from echomind.domain.ports import IBondDepthStore
from echomind.mind.bond_adapt import normalize_group
from echomind.mind.bond_features import depth_from_stats


async def _load_stats(
    store: IBondDepthStore, bonds: dict[str, SocialBondProfile]
) -> dict[str, BondDepthStats]:
    loaded: dict[str, BondDepthStats] = {}
    for uid, bond in bonds.items():
        row = await store.get_stats(bond.chat_key, uid)
        if row is not None:
            loaded[uid] = row
    return loaded


def _blend(stats: BondDepthStats, rank: float) -> float:
    """Average the absolute depth with the group-relative rank (L1 normalization)."""
    blended = 0.5 * depth_from_stats(stats) + 0.5 * 100.0 * rank
    return round(max(0.0, min(100.0, blended)), 2)


async def attach_bond_depth(
    store: IBondDepthStore | None, bonds: dict[str, SocialBondProfile]
) -> dict[str, SocialBondProfile]:
    """Fill `bond_depth` (absolute + group-relative) into each bond; no-op without a store."""
    if store is None or not bonds:
        return bonds
    stats = await _load_stats(store, bonds)
    ranks = dict(
        zip(stats, (n.frequency for n in normalize_group(tuple(stats.values()))), strict=True)
    )
    return {
        uid: bond if uid not in stats
        else bond.model_copy(update={"bond_depth": _blend(stats[uid], ranks[uid])})
        for uid, bond in bonds.items()
    }
