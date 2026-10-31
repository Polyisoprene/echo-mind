"""Temporal evolution of affect and drives: half-life decay and exogenous drift."""

from __future__ import annotations

from echomind.domain.models import AffectiveVector, DriveState, WorkingSnapshot
from echomind.mind.circadian import resolve_circadian_phase


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, round(val, 2)))


def _pull(current: float, target: float, rate: float = 0.08) -> float:
    return round((target - current) * rate, 2)


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
