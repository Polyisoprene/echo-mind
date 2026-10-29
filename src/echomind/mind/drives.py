"""M3.3/M24.1 Coupled Homeostatic RL Drives, Free-Energy Valence & Triadic Jealousy Engine."""

from __future__ import annotations

import datetime
import re

from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    Percept,
    PlasticParamSpec,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.mind.circadian import resolve_circadian_phase

CST = datetime.timezone(datetime.timedelta(hours=8))
PRAISE_PATTERN = re.compile(
    r"可爱|真棒|好棒|厉害|喜欢|真好|真乖|聪明|好看|漂亮|宠|贴|香|温柔|能干|靠谱|亲亲|抱抱|贴贴|老婆|宝贝|比你|多一点|好听|摸摸"
)
RIVAL_CRITIC_RE = re.compile(r"太吵|太笨|太傻|散养|不如你|还是回音|还是尾尾|乱回|烦人")
SCOLD_OR_DOUBT_RE = re.compile(
    r"^(?:[？?]+)$|胡乱回复|乱回|胡扯|答非所问|在干什么|搞错了|说错了|你真笨|闭嘴"
)
QUESTION_PATTERN = re.compile(r"为什么|是什么|怎么回事|啥意思|什么梗|知道吗|见过吗")


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, round(val, 2)))


def _pull(current: float, target: float, rate: float = 0.08) -> float:
    return round((target - current) * rate, 2)


def compute_care_weight(
    sender_id: str, owner_qq: str, bond: SocialBondProfile | None = None
) -> float:
    """Compute continuous care/importance weight w_care(u) in [0.0, 1.0] for any person."""
    if owner_qq and sender_id == owner_qq:
        return 1.0
    if bond is None or bond.is_rival:
        return 0.0
    return round(max(0.0, min(0.88, ((bond.affinity_score - 38.0) / 70.0) * bond.trust_score)), 3)


def compute_aversion_susceptibility(
    sender_id: str, owner_qq: str, bond: SocialBondProfile | None = None
) -> float:
    """Compute aversion/irritation susceptibility w_aversion(u) in [0.35, 1.75]."""
    if owner_qq and sender_id == owner_qq:
        return 0.35
    if bond is None:
        return 1.0
    raw = 1.35 - (bond.affinity_score / 110.0) + (0.82 - bond.trust_score)
    return round(max(0.40, min(1.75, raw)), 3)


def _mentions_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(r in text for r in terms if r)


def _is_rival_speaker(percept: Percept, terms: tuple[str, ...]) -> bool:
    return any(r in percept.sender_name or r == percept.sender_id for r in terms if r)


def _praises_third_party(percept: Percept, bot_name: str) -> bool:
    if not PRAISE_PATTERN.search(percept.text):
        return False
    quoted_other = bool(percept.quoted_message_id) and not percept.is_quoted_me
    return quoted_other or ("@" in percept.text and bot_name not in percept.text)


def evaluate_triadic_jealousy(
    percept: Percept, w_care: float, rivals: tuple[str, ...], bot_name: str = "回音"
) -> tuple[float, str]:
    """Salovey Triadic Jealousy Appraisal for ANY cared-about person (w_care >= 0.15)."""
    text = percept.text
    all_rivals = (*rivals, "别的AI", "别的机器人")
    if _is_rival_speaker(percept, all_rivals):
        return 2.5, ""
    if w_care < 0.15:
        return -1.2, ""
    mentions_rival = _mentions_any(text, all_rivals)
    praises_other = _praises_third_party(percept, bot_name)
    if not mentions_rival and not praises_other:
        return round(-1.2 * w_care, 2), ""
    if RIVAL_CRITIC_RE.search(text):
        return round(-12.0 * w_care, 2), f"因{percept.sender_name}偏袒自己而暗爽消醋"
    if PRAISE_PATTERN.search(text) or praises_other:
        return round(22.0 * w_care, 2), f"因在意的人({percept.sender_name})夸别人而吃醋"
    own_msg = (round(16.0 * w_care, 2), f"在意{percept.sender_name}提起其他AI")
    return own_msg if w_care >= 0.9 else (0.0, "")


def check_owner_jealousy_trigger(
    percept: Percept, owner_qq: str, rivals: tuple[str, ...], bot_name: str = "回音"
) -> bool:
    """Detect whether the owner just praised/flirted with or mentioned a rival positively."""
    if not owner_qq or percept.sender_id != owner_qq:
        return False
    jd, _ = evaluate_triadic_jealousy(percept, 1.0, rivals, bot_name)
    return jd > 0.0


def _curiosity_impulse(
    cur_val: float,
    triggers: tuple[Percept, ...],
    unknown_terms: tuple[str, ...],
    rate: float,
    *,
    energy: float = 75.0,
    irritation: float = 0.0,
) -> float:
    if energy < 32.0 or irritation > 60.0:
        return -2.5
    if unknown_terms:
        return len(unknown_terms) * (rate / 8.0)
    has_q = any(
        (len(p.text.strip()) >= 4 and bool(QUESTION_PATTERN.search(p.text))) or bool(p.media)
        for p in triggers
    )
    if has_q:
        return 5.5
    return _pull(cur_val, 32.0, 0.10)


def circadian_energy_target(now_ms: int | None = None) -> float:
    """Return Borbély Two-Process continuous circadian resting energy target."""
    return resolve_circadian_phase(now_ms).energy_target


def _evaluate_turn_rpe_and_soothing(
    triggers: tuple[Percept, ...],
    w_care: float,
    j_delta: float,
    att_val: float,
) -> tuple[float, float, float]:
    joined = " ".join(p.text.strip() for p in triggers)
    praise_hit = bool(PRAISE_PATTERN.search(joined)) and j_delta <= 0.0
    scold_hit = bool(SCOLD_OR_DOUBT_RE.search(joined))
    r_actual = -0.42 if scold_hit else (0.58 if praise_hit else 0.14)
    r_exp = 0.16 * w_care
    rpe_v = round((r_actual - r_exp) * (0.65 + 0.85 * w_care) * 14.0, 2)
    if w_care >= 0.20 and r_actual >= 0.0 and j_delta <= 0.0:
        soothe = round(min(18.0, max(2.5, att_val * 0.22 * w_care)), 2)
        shy_b = round(9.5 * (0.4 + 0.6 * w_care), 2) if praise_hit else 0.0
        return rpe_v + round(soothe * 0.35, 2), -soothe, shy_b
    att_d = round(0.25 * max(0.0, j_delta) + (1.2 if w_care >= 0.20 else 0.2), 2)
    return rpe_v, att_d, 0.0


def _build_coupled_vectors(
    aff: AffectiveVector, drv: DriveState, *,
    w_care: float, j_delta: float, v_rpe: float,
    att_delta: float, shy_boost: float, cur_d: float,
) -> tuple[AffectiveVector, DriveState]:
    new_j = _clamp(aff.jealousy + j_delta)
    irr_spill = round(0.18 * max(0.0, j_delta), 2)
    new_irr = _clamp(aff.irritation * 0.85 + irr_spill - (2.5 * w_care if v_rpe > 2.0 else 0.8))
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


def _max_triadic_jealousy(
    triggers: tuple[Percept, ...],
    owner_qq: str,
    rivals: tuple[str, ...],
    bonds_map: dict[str, SocialBondProfile] | None,
) -> tuple[float, str]:
    best_j, best_t = 0.0, ""
    for p in triggers:
        p_care = compute_care_weight(
            p.sender_id, owner_qq, bonds_map.get(p.sender_id) if bonds_map else None
        )
        jd, jt = evaluate_triadic_jealousy(p, p_care, rivals)
        if abs(jd) > abs(best_j):
            best_j, best_t = jd, jt
    return best_j, best_t


def apply_turn_affect_and_drives(
    snapshot: WorkingSnapshot,
    triggers: tuple[Percept, ...],
    owner_qq: str,
    rivals: tuple[str, ...],
    unknown_terms: tuple[str, ...] = (),
    *,
    jealousy_sens: float = 1.2,
    curiosity_rate: float = 65.0,
    bonds_map: dict[str, SocialBondProfile] | None = None,
    params: dict[str, PlasticParamSpec] | None = None,
) -> WorkingSnapshot:
    """Update 5D affect and 4D drives via HRRL Homeostasis, Free-Energy RPE & 5x5 Coupling."""
    _ = params
    aff, drv = snapshot.affect, snapshot.drives
    last_uid = triggers[-1].sender_id if triggers else ""
    w_care = compute_care_weight(last_uid, owner_qq, bonds_map.get(last_uid) if bonds_map else None)
    j_raw, j_thought = _max_triadic_jealousy(triggers, owner_qq, rivals, bonds_map)
    j_delta = round(j_raw * (jealousy_sens if j_raw > 0 else 1.0), 2)
    v_rpe, att_delta, shy_boost = _evaluate_turn_rpe_and_soothing(
        triggers, w_care, j_delta, drv.attachment
    )
    cur_d = _curiosity_impulse(
        drv.curiosity, triggers, unknown_terms, curiosity_rate,
        energy=aff.energy, irritation=aff.irritation,
    )
    new_aff, new_drv = _build_coupled_vectors(
        aff, drv, w_care=w_care, j_delta=j_delta,
        v_rpe=v_rpe, att_delta=att_delta, shy_boost=shy_boost, cur_d=cur_d,
    )
    merged_q = tuple(list(dict.fromkeys([*snapshot.curiosity_queue, *unknown_terms]))[-5:])
    return snapshot.model_copy(
        update={
            "affect": new_aff,
            "drives": new_drv,
            "curiosity_queue": merged_q,
            "inner_thought": j_thought or snapshot.inner_thought,
        }
    )


def apply_temporal_decay_and_circadian(
    snapshot: WorkingSnapshot, elapsed_minutes: float, now_ms: int | None = None
) -> WorkingSnapshot:
    """Evolve affect and drives across real elapsed time (half-life decay & circadian rhythm)."""
    if elapsed_minutes <= 1.0:
        return snapshot
    aff, drv = snapshot.affect, snapshot.drives
    dt_cap = min(elapsed_minutes, 180.0)
    decay = 0.5 ** (dt_cap / 30.0)
    phase = resolve_circadian_phase(now_ms)
    v_pull = _pull(aff.valence, 60.0, min(0.4, dt_cap * 0.012))
    new_aff = AffectiveVector(
        valence=_clamp(aff.valence + v_pull, -100.0, 100.0),
        energy=_clamp(aff.energy + _pull(aff.energy, phase.energy_target, min(0.5, dt_cap * 0.02))),
        jealousy=_clamp(aff.jealousy * decay), shyness=_clamp(18.0 + (aff.shyness - 18.0) * decay),
        irritation=_clamp(aff.irritation * decay),
    )
    att_target = 78.0 + phase.attachment_bias
    att_step = max(0.0, (att_target - drv.attachment) * min(0.35, dt_cap * 0.008))
    new_att = _clamp(drv.attachment + att_step, 18.0, 92.0)
    new_j_drv = _clamp(new_aff.jealousy * (0.55 + 0.45 * (new_att / 100.0)))
    new_drv = DriveState(
        curiosity=_clamp(drv.curiosity + min(10.0, dt_cap * 0.3) + phase.curiosity_bias * 0.25),
        attachment=new_att, jealousy_drive=new_j_drv,
        social_expression=_clamp(
            drv.social_expression + min(6.0, dt_cap * 0.15) + phase.social_bias * 0.25
        ),
    )
    use_p = phase.is_asleep or dt_cap >= 25.0
    act = phase.default_activity if use_p else snapshot.current_activity
    upd = {"affect": new_aff, "drives": new_drv, "current_activity": act}
    return snapshot.model_copy(update=upd)


def apply_exogenous_surf_affect(
    snapshot: WorkingSnapshot, unseen_line: str, *, shared_to_chat: bool = False
) -> WorkingSnapshot:
    """Update mood, satiate curiosity/expression drives, and refresh activity from surfing."""
    aff, drv = snapshot.affect, snapshot.drives
    new_aff = AffectiveVector(
        valence=_clamp(aff.valence + 7.5, -100.0, 100.0), energy=_clamp(aff.energy - 1.0),
        jealousy=_clamp(aff.jealousy - 4.0), shyness=aff.shyness,
        irritation=_clamp(aff.irritation - 10.0),
    )
    new_drv = DriveState(
        curiosity=_clamp(drv.curiosity - 26.0), attachment=drv.attachment,
        jealousy_drive=_clamp(new_aff.jealousy * (0.55 + 0.45 * (drv.attachment / 100.0))),
        social_expression=_clamp(drv.social_expression - (28.0 if shared_to_chat else 8.0)),
    )
    act = (
        "刚跟大家分享完新鲜事，正戴着耳机听歌休息"
        if (shared_to_chat or not unseen_line)
        else f"刚在B站刷到：{unseen_line[:110]}"
    )
    upd = {"affect": new_aff, "drives": new_drv, "current_activity": act}
    return snapshot.model_copy(update=upd)
