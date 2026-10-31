"""M3.3/M26.2 Pure Homeostatic RL Drives & 5x5 Coupled Affective Engine (Zero Lexicons)."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    Percept,
    PlasticParamSpec,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.mind.bond_depth import care_weight
from echomind.mind.circadian import resolve_circadian_phase

if TYPE_CHECKING:
    from echomind.mind.subconscious_probe import SubconsciousChordResult

CST = datetime.timezone(datetime.timedelta(hours=8))

# param: convention:persona-reunion-gap - 30 min sits beyond the observed p99 message
# gap (1,144 s over 5,850 gaps in data/echomind.db), so soothing fires on a genuine
# reunion rather than on every ordinary turn.
REUNION_GAP_MIN = 30.0


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, round(val, 2)))


def _pull(current: float, target: float, rate: float = 0.08) -> float:
    return round((target - current) * rate, 2)


def compute_care_weight(sender_id: str, bond: SocialBondProfile | None = None) -> float:
    """Compute continuous care/importance weight w_care(u) in [0.0, 1.0] for any person."""
    if bond is None or bond.is_rival:
        return 0.0
    return care_weight(bond.affinity_score, bond.trust_score, bond.bond_depth)


def compute_aversion_susceptibility(
    sender_id: str, bond: SocialBondProfile | None = None
) -> float:
    """Compute aversion/irritation susceptibility w_aversion(u) in [0.35, 1.75]."""
    if bond is None:
        return 1.0
    raw = 1.35 - (bond.affinity_score / 110.0) + (0.82 - bond.trust_score)
    return round(max(0.40, min(1.75, raw)), 3)


def _is_rival_speaker(percept: Percept, terms: tuple[str, ...]) -> bool:
    return any(r in percept.sender_name or r == percept.sender_id for r in terms if r)


def _chord_jealousy_delta(
    percept: Percept, w_care: float, chord: SubconsciousChordResult
) -> tuple[float, str]:
    if chord.jealousy > 0:
        delta = round(8.5 * chord.jealousy * max(0.20, w_care), 2)
        return delta, chord.thought or f"因在意的人({percept.sender_name})偏心别人而吃醋"
    return round(5.5 * chord.jealousy * max(0.30, w_care), 2), chord.thought or "被偏爱消醋"


def evaluate_triadic_jealousy(
    percept: Percept, w_care: float, rivals: tuple[str, ...],
    *, chord: SubconsciousChordResult | None = None,
) -> tuple[float, str]:
    """Salovey Triadic Jealousy Appraisal driven by SubconsciousChordResult & rival identity."""
    if _is_rival_speaker(percept, rivals):
        return 2.5, ""
    if w_care < 0.15:
        return -1.2, ""
    if chord is not None and chord.jealousy != 0:
        return _chord_jealousy_delta(percept, w_care, chord)
    mentions_rival = any(r and r in percept.text for r in rivals)
    quoted_other = bool(percept.quoted_message_id) and not percept.is_quoted_me
    if mentions_rival or quoted_other:
        return round(18.0 * w_care, 2), f"因在意的人({percept.sender_name})关注其他对象而吃醋"
    return round(-1.2 * w_care, 2), ""


def check_owner_jealousy_trigger(
    percept: Percept, rivals: tuple[str, ...],
    *, chord: SubconsciousChordResult | None = None,
) -> bool:
    """Detect whether a deeply-cared speaker just triggered triadic jealousy."""
    jd, _ = evaluate_triadic_jealousy(percept, 1.0, rivals, chord=chord)
    return jd > 0.0


def circadian_energy_target(now_ms: int | None = None) -> float:
    """Return Borbély Two-Process continuous circadian resting energy target."""
    return resolve_circadian_phase(now_ms).energy_target


def _curiosity_impulse(
    cur_val: float, triggers: tuple[Percept, ...], unknown_terms: tuple[str, ...], rate: float,
    *, chord: SubconsciousChordResult | None = None, energy: float = 75.0, irritation: float = 0.0,
) -> float:
    if energy < 32.0 or irritation > 60.0:
        return -2.5
    if unknown_terms:
        return len(unknown_terms) * (rate / 8.0)
    if chord is not None and chord.curiosity > 0:
        return 4.5 * chord.curiosity
    return 5.5 if any(bool(p.media) for p in triggers) else _pull(cur_val, 32.0, 0.10)


def _extract_chord_components(
    chord: SubconsciousChordResult | None, is_poke: bool, speaker_aff: float, curr_irr: float
) -> tuple[int, int, int, int]:
    c_joy = chord.joy if chord else (2 if is_poke else 0)
    c_hurt = chord.hurt if chord else 0
    c_shy = chord.shyness if chord else (1 if is_poke else 0)
    c_ann = chord.annoyance if chord else 0
    if (speaker_aff < 30.0 or curr_irr >= 45.0) and c_shy > 0:
        return c_joy, c_hurt, 0, max(c_ann, c_shy + 1)
    return c_joy, c_hurt, c_shy, c_ann


def _chord_rpe_and_soothing(
    w_care: float, w_aver: float, j_delta: float, att_val: float,
    *, speaker_aff: float, curr_irr: float, chord: SubconsciousChordResult | None,
    is_poke: bool, is_reunion: bool,
) -> tuple[float, float, float, float]:
    c_joy, c_hurt, c_shy, c_ann = _extract_chord_components(chord, is_poke, speaker_aff, curr_irr)
    neutral_base = 0.12 if (c_joy == 0 and c_hurt == 0 and c_ann == 0) else 0.0
    r_actual = 0.25 * c_joy - 0.28 * c_hurt - 0.25 * c_ann + neutral_base
    rpe_v = round((r_actual - 0.16 * w_care) * (0.65 + 0.85 * w_care) * 14.0, 2)
    irr_d = round(6.5 * c_ann * w_aver - 2.0 * c_joy * (0.4 + 0.6 * w_care), 2)
    shy_b = round(5.5 * c_shy * (0.35 + 0.65 * w_care), 2)
    if is_reunion and w_care >= 0.20 and r_actual >= 0.0 and j_delta <= 0.0:
        soothe = round(min(18.0, max(2.5, att_val * 0.22 * w_care * (1.0 + 0.25 * c_joy))), 2)
        return rpe_v + round(soothe * 0.35, 2), -soothe, shy_b, irr_d
    att_d = round(0.25 * max(0.0, j_delta) + (1.2 if w_care >= 0.20 else 0.2), 2)
    return rpe_v, att_d, shy_b, irr_d


def _build_coupled_vectors(aff: AffectiveVector, drv: DriveState, *,
    w_care: float, j_delta: float, v_rpe: float,
    att_delta: float, shy_boost: float, irr_delta: float, cur_d: float,
) -> tuple[AffectiveVector, DriveState]:
    new_j = _clamp(aff.jealousy * 0.88 + j_delta * (1.0 - aff.jealousy / 120.0))
    irr_spill = round(0.18 * max(0.0, j_delta), 2)
    soothe_irr = 1.8 * w_care if v_rpe > 2.0 else 0.6
    new_irr = _clamp(aff.irritation * 0.85 + irr_delta + irr_spill - soothe_irr)
    v_cross = v_rpe - round(0.32 * max(0.0, j_delta) + 0.25 * new_irr, 2)
    new_val = _clamp(aff.valence + _pull(aff.valence, 62.0, 0.08) + v_cross, -100.0, 100.0)
    shy_cross = shy_boost + round(0.15 * max(0.0, j_delta) - 0.30 * new_irr, 2)
    new_shy = _clamp(aff.shyness + _pull(aff.shyness, 22.0, 0.10) + shy_cross)
    new_eng = _clamp(aff.energy + _pull(aff.energy, circadian_energy_target(), 0.14) - 1.5)
    new_att = _clamp(drv.attachment + _pull(drv.attachment, 52.0, 0.05) + att_delta, 18.0, 95.0)
    new_j_drv = _clamp(
        new_j * (0.55 + 0.45 * (new_att / 100.0)) * (1.0 - 0.25 * (new_shy / 100.0))
    )
    soc_cross = round(
        0.06 * (new_val - 50.0) - 0.22 * new_irr - 0.12 * max(0.0, new_shy - 45.0), 2
    )
    new_soc = _clamp(drv.social_expression + _pull(drv.social_expression, 48.0, 0.10) + soc_cross)
    return (
        AffectiveVector(
            valence=new_val, energy=new_eng, jealousy=new_j, shyness=new_shy, irritation=new_irr
        ),
        DriveState(
            curiosity=_clamp(drv.curiosity + cur_d), attachment=new_att,
            jealousy_drive=new_j_drv, social_expression=new_soc,
        ),
    )


def _format_spillover(
    prev_thought: str, chord: SubconsciousChordResult | None, j_thought: str, speaker: str
) -> str:
    if chord is not None and (
        abs(chord.jealousy) >= 1 or chord.hurt >= 1 or chord.annoyance >= 1 or chord.joy >= 2
    ):
        sub = f"（潜台词：{chord.subtext}）" if chord.subtext else ""
        return f"[源头:{speaker} · 🎨{chord.shade}] {chord.thought}{sub}"[:140]
    return j_thought or prev_thought


def _max_batch_jealousy(
    triggers: tuple[Percept, ...], rivals: tuple[str, ...],
    bonds_map: dict[str, SocialBondProfile] | None, chord: SubconsciousChordResult | None,
) -> tuple[float, str]:
    best_j, best_t = 0.0, ""
    for p in triggers:
        p_care = compute_care_weight(
            p.sender_id, bonds_map.get(p.sender_id) if bonds_map else None
        )
        jd, jt = evaluate_triadic_jealousy(p, p_care, rivals, chord=chord)
        if abs(jd) > abs(best_j):
            best_j, best_t = jd, jt
    return best_j, best_t


def _appraisal_context(
    bond: SocialBondProfile | None, last: Percept | None
) -> tuple[float, float, float, bool]:
    """Care weight, aversion susceptibility, speaker affinity and reunion flag."""
    uid = bond.user_id if bond is not None else ""
    w_care = compute_care_weight(uid, bond)
    w_aver = compute_aversion_susceptibility(uid, bond)
    s_aff = 9999.0 if w_care >= 0.99 else (bond.affinity_score if bond else 35.0)
    last_seen = bond.last_seen_ms if bond is not None else 0
    gap_min = 0.0 if last is None or last_seen <= 0 else (last.timestamp_ms - last_seen) / 60_000.0
    return w_care, w_aver, s_aff, gap_min >= REUNION_GAP_MIN


def apply_turn_affect_and_drives(
    snapshot: WorkingSnapshot, triggers: tuple[Percept, ...],
    rivals: tuple[str, ...], unknown_terms: tuple[str, ...] = (), *,
    jealousy_sens: float = 1.2, curiosity_rate: float = 65.0,
    bonds_map: dict[str, SocialBondProfile] | None = None,
    params: dict[str, PlasticParamSpec] | None = None,
    chord: SubconsciousChordResult | None = None,
) -> WorkingSnapshot:
    """Update 5D affect and 4D drives via HRRL Homeostasis, Free-Energy RPE & 6D Chord."""
    _ = params
    aff, drv = snapshot.affect, snapshot.drives
    last = triggers[-1] if triggers else None
    last_uid = last.sender_id if last else ""
    bond = bonds_map.get(last_uid) if bonds_map else None
    w_care, w_aver, s_aff, is_reunion = _appraisal_context(bond, last)
    j_raw, j_thought = _max_batch_jealousy(triggers, rivals, bonds_map, chord)
    j_delta = round(j_raw * (jealousy_sens if j_raw > 0 else 1.0), 2)
    v_rpe, att_delta, shy_boost, irr_delta = _chord_rpe_and_soothing(
        w_care, w_aver, j_delta, drv.attachment, speaker_aff=s_aff, curr_irr=aff.irritation,
        chord=chord, is_poke=any(p.is_poke_me for p in triggers), is_reunion=is_reunion,
    )
    cur_d = _curiosity_impulse(
        drv.curiosity, triggers, unknown_terms, curiosity_rate,
        chord=chord, energy=aff.energy, irritation=aff.irritation,
    )
    new_aff, new_drv = _build_coupled_vectors(
        aff, drv, w_care=w_care, j_delta=j_delta, v_rpe=v_rpe,
        att_delta=att_delta, shy_boost=shy_boost, irr_delta=irr_delta, cur_d=cur_d,
    )
    merged_q = tuple(list(dict.fromkeys([*snapshot.curiosity_queue, *unknown_terms]))[-5:])
    speaker = (last.sender_name or last.sender_id) if last else ""
    spill = _format_spillover(snapshot.inner_thought, chord, j_thought, speaker)
    return snapshot.model_copy(
        update={
            "affect": new_aff, "drives": new_drv,
            "curiosity_queue": merged_q, "inner_thought": spill,
        }
    )
