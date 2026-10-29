"""M3.3 Affective Half-Life Decay, Jealousy Trigger & Four Intrinsic Drives Engine."""

from __future__ import annotations

import datetime
import re

from echomind.domain.models import AffectiveVector, DriveState, Percept, WorkingSnapshot
from echomind.mind.circadian import resolve_circadian_phase

CST = datetime.timezone(datetime.timedelta(hours=8))

PRAISE_PATTERN = re.compile(
    r"可爱|真棒|好棒|厉害|喜欢|真好|真乖|聪明|好看|漂亮|宠|贴|香|温柔|能干|靠谱|亲亲|抱抱|贴贴|老婆|宝贝|比你|多一点"
)
QUESTION_PATTERN = re.compile(r"[？?]|为什么|是什么|怎么|啥意思|什么梗|知道吗|见过吗")


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, round(val, 2)))


def _pull(current: float, target: float, rate: float = 0.08) -> float:
    return round((target - current) * rate, 2)


def check_owner_jealousy_trigger(
    percept: Percept, owner_qq: str, rivals: tuple[str, ...], bot_name: str = "回音"
) -> bool:
    """Detect whether the owner just praised/flirted with or mentioned a rival."""
    if not owner_qq or percept.sender_id != owner_qq:
        return False
    text = percept.text
    all_rivals = (*rivals, "汐", "豆包", "别的AI", "别的机器人")
    if any(r and r in text for r in all_rivals):
        return True
    if not PRAISE_PATTERN.search(text):
        return False
    return (bool(percept.quoted_message_id) and not percept.is_quoted_me) or (
        "@" in text and bot_name not in text
    )


def _compute_social_deltas(
    jealousy_hit: bool, rival_spoke: bool, owner_spoke: bool, jealousy_sens: float
) -> tuple[float, float, float]:
    if jealousy_hit:
        return 18.0 * jealousy_sens, -8.0, 4.0
    if rival_spoke:
        return 4.5 * jealousy_sens, -1.0, 1.5
    if owner_spoke:
        return -0.8, 5.0, 3.0
    return -0.6, 0.8, 0.5


def _curiosity_impulse(
    cur_val: float, triggers: tuple[Percept, ...], unknown_terms: tuple[str, ...], rate: float
) -> float:
    if unknown_terms:
        return len(unknown_terms) * (rate / 8.0)
    has_q = any(QUESTION_PATTERN.search(p.text) or bool(p.media) for p in triggers)
    if has_q:
        return 6.5
    return _pull(cur_val, 28.0, 0.10)


def circadian_energy_target(now_ms: int | None = None) -> float:
    """Return Borbély Two-Process continuous circadian resting energy target."""
    return resolve_circadian_phase(now_ms).energy_target


def _next_affect(
    aff: AffectiveVector, v_delta: float, new_jealousy: float, owner_spoke: bool
) -> AffectiveVector:
    return AffectiveVector(
        valence=_clamp(aff.valence + _pull(aff.valence, 72.0, 0.06) + v_delta, -100.0, 100.0),
        energy=_clamp(aff.energy + _pull(aff.energy, circadian_energy_target(), 0.14) - 1.8),
        jealousy=new_jealousy,
        shyness=_clamp(
            aff.shyness + _pull(aff.shyness, 35.0, 0.06) + (4.0 if owner_spoke else -0.8)
        ),
        irritation=_clamp(aff.irritation - 1.0),
    )


def apply_turn_affect_and_drives(
    snapshot: WorkingSnapshot,
    triggers: tuple[Percept, ...],
    owner_qq: str,
    rivals: tuple[str, ...],
    unknown_terms: tuple[str, ...] = (),
    *,
    jealousy_sens: float = 1.2,
    curiosity_rate: float = 65.0,
) -> WorkingSnapshot:
    """Update working affect, jealousy, curiosity queue, and intrinsic drives for a turn."""
    aff, drv = snapshot.affect, snapshot.drives
    all_rivals = (*rivals, "汐", "豆包")
    j_hit = any(check_owner_jealousy_trigger(p, owner_qq, all_rivals) for p in triggers)
    r_spoke = any(any(r in p.sender_name for r in all_rivals) for p in triggers)
    o_spoke = bool(owner_qq) and any(p.sender_id == owner_qq for p in triggers)
    j_delta, v_delta, att_delta = _compute_social_deltas(j_hit, r_spoke, o_spoke, jealousy_sens)
    cur_delta = _curiosity_impulse(drv.curiosity, triggers, unknown_terms, curiosity_rate)
    new_j = _clamp(aff.jealousy + j_delta)
    new_drv = DriveState(
        curiosity=_clamp(drv.curiosity + cur_delta),
        attachment=_clamp(drv.attachment + _pull(drv.attachment, 78.0, 0.06) + att_delta),
        jealousy_drive=new_j,
        social_expression=_clamp(
            drv.social_expression + _pull(drv.social_expression, 68.0, 0.08) + 1.8
        ),
    )
    merged_q = tuple(list(dict.fromkeys([*snapshot.curiosity_queue, *unknown_terms]))[-5:])
    return snapshot.model_copy(
        update={
            "affect": _next_affect(aff, v_delta, new_j, o_spoke),
            "drives": new_drv,
            "curiosity_queue": merged_q,
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
    v_pull = _pull(aff.valence, 62.0, min(0.4, dt_cap * 0.012))
    new_aff = AffectiveVector(
        valence=_clamp(aff.valence + v_pull, -100.0, 100.0),
        energy=_clamp(aff.energy + _pull(aff.energy, phase.energy_target, min(0.5, dt_cap * 0.02))),
        jealousy=_clamp(aff.jealousy * decay),
        shyness=_clamp(18.0 + (aff.shyness - 18.0) * decay),
        irritation=_clamp(aff.irritation * decay),
    )
    new_drv = DriveState(
        curiosity=_clamp(drv.curiosity + min(10.0, dt_cap * 0.3) + phase.curiosity_bias * 0.25),
        attachment=_clamp(drv.attachment + min(8.0, dt_cap * 0.2) + phase.attachment_bias * 0.25),
        jealousy_drive=new_aff.jealousy,
        social_expression=_clamp(
            drv.social_expression + min(6.0, dt_cap * 0.15) + phase.social_bias * 0.25
        ),
    )
    use_phase_act = phase.is_asleep or dt_cap >= 25.0
    act = phase.default_activity if use_phase_act else snapshot.current_activity
    return snapshot.model_copy(
        update={"affect": new_aff, "drives": new_drv, "current_activity": act}
    )


def apply_exogenous_surf_affect(
    snapshot: WorkingSnapshot, unseen_line: str, *, shared_to_chat: bool = False
) -> WorkingSnapshot:
    """Update mood, satiate curiosity/expression drives, and refresh activity from surfing."""
    aff, drv = snapshot.affect, snapshot.drives
    new_aff = AffectiveVector(
        valence=_clamp(aff.valence + 7.5, -100.0, 100.0),
        energy=_clamp(aff.energy - 1.0),
        jealousy=_clamp(aff.jealousy - 4.0),
        shyness=aff.shyness,
        irritation=_clamp(aff.irritation - 10.0),
    )
    new_drv = DriveState(
        curiosity=_clamp(drv.curiosity - 26.0),
        attachment=drv.attachment,
        jealousy_drive=new_aff.jealousy,
        social_expression=_clamp(drv.social_expression - (28.0 if shared_to_chat else 8.0)),
    )
    if shared_to_chat or not unseen_line:
        act = "刚跟大家分享完新鲜事，正戴着耳机听歌休息"
    else:
        act = f"刚在B站刷到：{unseen_line[:110]}"
    return snapshot.model_copy(
        update={"affect": new_aff, "drives": new_drv, "current_activity": act}
    )
