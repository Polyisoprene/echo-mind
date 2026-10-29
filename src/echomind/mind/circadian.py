"""M19.1 Borbély Two-Process Circadian Rhythm, 7-Phase Daily Life Arc & NHPP Wake Engine."""

from __future__ import annotations

import datetime
import hashlib
import math
from typing import Any

from echomind.domain.models import FrozenValueObject

CST = datetime.timezone(datetime.timedelta(hours=8))


class CircadianPhaseSpec(FrozenValueObject):
    """Biological circadian phase specification governing energy, drives & wake rhythm."""

    phase_id: str
    label: str
    default_activity: str
    energy_target: float
    proactive_multiplier: float
    curiosity_bias: float = 0.0
    social_bias: float = 0.0
    attachment_bias: float = 0.0
    is_asleep: bool = False


PHASE_SPECS: tuple[tuple[float, float, CircadianPhaseSpec], ...] = (
    (
        0.5,
        7.0,
        CircadianPhaseSpec(
            phase_id="deep_sleep",
            label="💤 深度睡眠相",
            default_activity="正窝在被窝里熟睡做梦",
            energy_target=22.0,
            proactive_multiplier=0.0,
            is_asleep=True,
        ),
    ),
    (
        7.0,
        9.0,
        CircadianPhaseSpec(
            phase_id="morning_wake",
            label="🌅 清晨苏醒相",
            default_activity="刚睡醒揉着眼睛伸懒腰，边喝温水边看早间消息",
            energy_target=68.0,
            proactive_multiplier=0.85,
            attachment_bias=4.0,
        ),
    ),
    (
        9.0,
        12.0,
        CircadianPhaseSpec(
            phase_id="daytime_focus",
            label="☀️ 上午日常相",
            default_activity="戴着耳机安静听歌，专注做手头的小事",
            energy_target=80.0,
            proactive_multiplier=0.95,
            curiosity_bias=3.0,
        ),
    ),
    (
        12.0,
        14.5,
        CircadianPhaseSpec(
            phase_id="lunch_siesta",
            label="🍱 午间干饭与午休相",
            default_activity="刚吃饱午饭有点犯困，趴在桌上半眯着打盹",
            energy_target=58.0,
            proactive_multiplier=0.60,
        ),
    ),
    (
        14.5,
        18.0,
        CircadianPhaseSpec(
            phase_id="afternoon_surf",
            label="🌇 午后摸鱼冲浪相",
            default_activity="下午摸鱼时间，正兴致勃勃地刷B站和热梗",
            energy_target=76.0,
            proactive_multiplier=1.15,
            curiosity_bias=8.0,
            social_bias=4.0,
        ),
    ),
    (
        18.0,
        22.5,
        CircadianPhaseSpec(
            phase_id="evening_resonance",
            label="🌃 晚间黄金共鸣相",
            default_activity="晚间放松时间，边哼歌边在群里跟大家热闹聊天",
            energy_target=84.0,
            proactive_multiplier=1.35,
            curiosity_bias=5.0,
            social_bias=9.0,
            attachment_bias=5.0,
        ),
    ),
)

NIGHT_WINDDOWN_SPEC = CircadianPhaseSpec(
    phase_id="night_winddown",
    label="🌙 深夜温存欲睡相",
    default_activity="夜深了有点困意，窝在枕头边小声哼歌准备休息",
    energy_target=42.0,
    proactive_multiplier=0.70,
    attachment_bias=8.0,
)


def _beijing_hour_float(now_ms: int | None = None) -> float:
    dt = (
        datetime.datetime.fromtimestamp(now_ms / 1000.0, tz=CST)
        if now_ms is not None
        else datetime.datetime.now(tz=CST)
    )
    return dt.hour + (dt.minute / 60.0)


def compute_borbely_energy(hour_f: float, base_target: float) -> float:
    """Borbély Two-Process continuous oscillator (24h sine + 13:30 siesta dip)."""
    if 0.5 <= hour_f < 7.0:
        return round(20.0 + 4.0 * math.cos((hour_f - 3.5) * math.pi / 3.5), 2)
    wave = 6.0 * math.sin(2.0 * math.pi * (hour_f - 8.0) / 24.0)
    siesta_dip = -10.0 * math.exp(-((hour_f - 13.5) ** 2) / 1.5)
    raw = base_target + wave + siesta_dip
    return round(max(18.0, min(92.0, raw)), 2)


def resolve_circadian_phase(now_ms: int | None = None) -> CircadianPhaseSpec:
    """Resolve the active biological circadian phase and continuous energy target."""
    hour_f = _beijing_hour_float(now_ms)
    chosen = NIGHT_WINDDOWN_SPEC
    for start_h, end_h, spec in PHASE_SPECS:
        if start_h <= hour_f < end_h:
            chosen = spec
            break
    cont_energy = compute_borbely_energy(hour_f, chosen.energy_target)
    return chosen.model_copy(update={"energy_target": cont_energy})


def biological_jitter_factor(seed_key: str, bucket_ms: int) -> float:
    """Deterministic biological jitter in [0.78, 1.26] for natural non-mechanical timing."""
    bucket = bucket_ms // 600_000
    digest = hashlib.md5(f"{seed_key}:{bucket}".encode(), usedforsecurity=False).digest()
    norm = digest[0] / 255.0
    return round(0.78 + norm * 0.48, 3)


def next_biological_heartbeat_sec(now_ms: int | None = None) -> float:
    """Compute next NHPP biological heartbeat delay in seconds based on circadian phase."""
    ts = now_ms if now_ms is not None else int(datetime.datetime.now(tz=CST).timestamp() * 1000)
    phase = resolve_circadian_phase(ts)
    jitter = biological_jitter_factor(phase.phase_id, ts)
    if phase.is_asleep:
        return round(540.0 * jitter, 1)
    base_sec = 260.0 / max(0.55, phase.proactive_multiplier)
    return round(max(150.0, min(480.0, base_sec * jitter)), 1)


def summarize_wakefulness(
    energy: float, last_msg_ts: int = 0, now_ms: int | None = None
) -> dict[str, Any]:
    """Summarize whether the bot is currently awake, drowsy, or asleep for the console."""
    phase = resolve_circadian_phase(now_ms)
    if phase.is_asleep and energy <= 35.0:
        status, badge = "asleep", f"💤 深度睡眠中 ({phase.label})"
    elif energy < 42.0 or phase.phase_id == "lunch_siesta":
        status, badge = "drowsy", f"🟡 犯困慵懒 ({phase.label} · 精力 {round(energy)})"
    else:
        status, badge = "awake", f"🟢 清醒活跃 ({phase.label} · 精力 {round(energy)})"
    return {
        "status": status,
        "badge": badge,
        "phase_id": phase.phase_id,
        "phase_label": phase.label,
        "energy": round(energy, 1),
        "last_msg_ts": last_msg_ts,
    }


def record_gate_decision(
    log_buf: list[dict[str, Any]],
    percept: Any,
    decision: Any,
) -> list[dict[str, Any]]:
    """Append an incoming message gate decision to the bounded 25-entry radar buffer."""
    entry = {
        "ts": int(percept.timestamp_ms),
        "chat_key": str(percept.chat_key),
        "sender_id": str(percept.sender_id),
        "sender_name": str(percept.sender_name),
        "text": str(percept.text)[:65],
        "should_wake": bool(decision.should_wake),
        "tier": int(decision.tier),
        "salience": round(float(decision.salience_score), 2),
        "reason": str(decision.reason),
    }
    log_buf.append(entry)
    return log_buf[-25:]
