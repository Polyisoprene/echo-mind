"""Stage 30 S30-4: relationship stance — a bounded shift of the *rendered* personality.

The stored 7D vector stays global (she is one person). For a specific interlocutor we shift a
few dimensions by at most STANCE_MAX_POINTS so the same traits read differently for a deeply
bonded person than for a stranger.

param: fit:pending - the weights below are engineering conventions awaiting calibration;
their *signs* are fixed by design (deeper bond ⇒ warmer, less guarded; higher trust ⇒ more
patient; higher affinity ⇒ more playful).
"""

from __future__ import annotations

import math

from echomind.domain.models import PlasticParamSpec, SocialBondProfile
from echomind.mind.person_level import PersonProfile, stance_from_profile

STANCE_MAX_POINTS = 8.0
# key -> (warmth_bias, patience_bias, play_bias)
STANCE_COEFFICIENTS: dict[str, tuple[float, float, float]] = {
    "persona_warmth": (1.0, 0.0, 0.0),
    "persona_tsundere": (-0.8, 0.0, 0.0),
    "persona_playfulness": (0.0, 0.0, 1.0),
    "persona_defiance": (0.0, -0.7, 0.0),
    "persona_confidence": (0.0, 0.0, 0.2),
}


def stance_vector(bond: SocialBondProfile) -> tuple[float, float, float]:
    """Map a bond ledger onto (warmth, patience, play) in [-1, 1]."""
    depth = bond.bond_depth / 100.0
    patience = (bond.trust_score - 0.5) * 2.0
    play = (bond.affinity_score - 50.0) / 50.0
    return (math.tanh(depth * 1.6), math.tanh(patience), math.tanh(play))


def stance_for(
    bonds_map: dict[str, SocialBondProfile] | None, sender_id: str
) -> tuple[float, float, float]:
    """Stance toward the person being answered (zeros when unknown)."""
    bond = (bonds_map or {}).get(sender_id)
    return stance_vector(bond) if bond is not None else (0.0, 0.0, 0.0)


def apply_stance(
    params: dict[str, PlasticParamSpec], sigma: tuple[float, float, float]
) -> dict[str, PlasticParamSpec]:
    """Return a shifted copy of the persona params; the stored values are never mutated."""
    if not any(sigma):
        return params
    shifted = dict(params)
    for key, coeffs in STANCE_COEFFICIENTS.items():
        spec = shifted.get(key)
        if spec is None:
            continue
        delta = STANCE_MAX_POINTS * sum(c * s for c, s in zip(coeffs, sigma, strict=True))
        value = max(spec.min_bound, min(spec.max_bound, spec.value + delta))
        shifted[key] = spec.model_copy(update={"value": round(value, 2)})
    return shifted


def apply_stance_for(
    params: dict[str, PlasticParamSpec],
    bonds_map: dict[str, SocialBondProfile] | None,
    sender_id: str,
    profiles: dict[str, PersonProfile] | None = None,
) -> dict[str, PlasticParamSpec]:
    """Warmth/patience from the person profile; play from the venue bond."""
    bond = (bonds_map or {}).get(sender_id)
    if bond is None:
        return params
    profile = (profiles or {}).get(sender_id)
    sigma = stance_from_profile(bond, profile) if profile is not None else stance_vector(bond)
    return apply_stance(params, sigma)
