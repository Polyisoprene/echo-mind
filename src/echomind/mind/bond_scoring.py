"""Attach earned bond depth to social bonds before the mind layers read them.

L1 within-group percentile normalization, L2 affine calibration of absolute depth onto the
group's rank scale, L3 empirical-Bayes shrinkage toward identity for thinly-observed groups,
L4 Page-Hinkley drift monitoring (alarm only, never auto-tunes).
"""

from __future__ import annotations

import logging

from echomind.domain.bond_stats import BondDepthStats, BondFeatures
from echomind.domain.models import SocialBondProfile
from echomind.domain.ports import IBondDepthStore
from echomind.mind.bond_adapt import (
    GroupCalibration,
    PageHinkley,
    apply_calibration,
    fit_affine,
    normalize_group,
    shrink_weights,
)
from echomind.mind.bond_features import depth_from_stats

logger = logging.getLogger(__name__)
SHRINK_TAU = 2.0
_DETECTORS: dict[str, PageHinkley] = {}


async def _load_stats(
    store: IBondDepthStore, bonds: dict[str, SocialBondProfile]
) -> dict[str, BondDepthStats]:
    loaded: dict[str, BondDepthStats] = {}
    for uid, bond in bonds.items():
        row = await store.get_stats(bond.chat_key, uid)
        if row is not None:
            loaded[uid] = row
    return loaded


def _calibrate(stats: dict[str, BondDepthStats], ranks: dict[str, float]) -> GroupCalibration:
    """L2+L3: fit absolute-depth → group-rank, then shrink thin groups toward identity."""
    depths = tuple(depth_from_stats(s) for s in stats.values())
    targets = tuple(100.0 * ranks[uid] for uid in stats)
    fitted = fit_affine(depths, targets)
    slope, offset = shrink_weights(
        (fitted.slope, fitted.offset), (1.0, 0.0), n_obs=len(stats), tau=SHRINK_TAU
    )
    return GroupCalibration(chat_key="", slope=round(slope, 4), offset=round(offset, 4),
                            n_obs=fitted.n_obs)


def _blend(stats: BondDepthStats, rank: float, calib: GroupCalibration) -> float:
    calibrated = apply_calibration(depth_from_stats(stats), calib)
    blended = 0.5 * calibrated + 0.5 * 100.0 * rank
    return round(max(0.0, min(100.0, blended)), 2)


def observe_group_drift(chat_key: str, mean_depth: float) -> bool:
    """L4: feed the group's mean depth into a Page-Hinkley detector; True on alarm."""
    detector = _DETECTORS.setdefault(chat_key, PageHinkley())
    alarmed = detector.update(mean_depth)
    if alarmed:
        logger.warning("bond-depth drift detected in %s (mean=%.1f)", chat_key, mean_depth)
    return alarmed


async def attach_bond_depth(
    store: IBondDepthStore | None, bonds: dict[str, SocialBondProfile]
) -> dict[str, SocialBondProfile]:
    """Fill `bond_depth` (calibrated + group-relative) into each bond; no-op without a store."""
    if store is None or not bonds:
        return bonds
    stats = await _load_stats(store, bonds)
    features = normalize_group(tuple(stats.values()))
    ranks: dict[str, float] = dict(
        zip(stats, (f.frequency for f in features), strict=True)
    )
    calib = _calibrate(stats, ranks)
    if stats:
        observe_group_drift(next(iter(bonds.values())).chat_key,
                            sum(ranks.values()) / len(ranks) * 100.0)
    enriched: dict[str, SocialBondProfile] = {}
    for uid, bond in bonds.items():
        if uid not in stats:
            enriched[uid] = bond
            continue
        depth = _blend(stats[uid], ranks[uid], calib)
        await store.set_bond_depth(bond.chat_key, uid, depth)
        enriched[uid] = bond.model_copy(update={"bond_depth": depth})
    return enriched


__all__ = ["attach_bond_depth", "observe_group_drift", "BondFeatures"]
