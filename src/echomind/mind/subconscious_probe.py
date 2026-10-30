"""M25.1 Subconscious 6D Emotional Chord Probe, Tensor Synthesis & Spillover."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from echomind.domain.models import (
    AffectiveVector,
    AttentionDecision,
    DriveState,
    FrozenValueObject,
    Percept,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.domain.ports import ILlmGateway
from echomind.mind.drives import (
    circadian_energy_target,
    compute_aversion_susceptibility,
    compute_care_weight,
)

JSON_EXTRACT_RE = re.compile(r"\{[\s\S]*\}")

CHORD_PROBE_SYS = (
    "你是「回音（小名尾尾）」大脑的潜意识多维情感和弦与语用感知中枢（蓝发傲娇少女）。\n"
    "请阅读【近期上下文】（仅作背景参考）与【最新消息】，严格只针对【最新消息】本身输出单行 JSON"
    "（使用 0~3 整数档位：0=无, 1=轻微, 2=明显, 3=强烈）：\n"
    "1. role (5选1)：\n"
    '   - "direct_to_me": 最新消息明确在跟我说话、问我或接我上一句话（若“回音”只是声学名词'
    "如“空间大有回音”，选 ambient_daily 且 topic_pull 填 0；若拿我举例讨论，选 about_me）。\n"
    '   - "about_me": 最新消息正在讨论关于我的事（设定/情感系统/表现），或正在当面夸/摸别的AI。\n'
    '   - "peer_dyadic": 群友之间一对一互聊/教学（如抠游戏帧数）、或跟别的机器人说话，与我无关。\n'
    '   - "ambient_daily": 群友个人的日常感慨/分享/表情包展示（没特定对别人说，也没聊我）。\n'
    '   - "noise": 无意义单字复读。\n'
    "2. topic_pull (0~3整数，话题或表情包吸引力)：0=枯燥他人私事/无关声学名词，1=普通日常，"
    "2=有趣公共话题/好玩表情包梗图/美食/音乐，3=极度吸引我的焦点话题。\n"
    "3. chord (6维情感和弦整数)：\n"
    '   - "joy" (0~3): 欣喜/温暖/被逗乐/看到有趣表情包\n'
    '   - "hurt" (0~3): 委屈/失落/被冷落忽视\n'
    '   - "jealousy" (-3~+3): 正数(1~3)=吃醋泛酸(当面夸/摸别的AI)；负数(-1~-3)=偏袒我时的暗爽消醋\n'
    '   - "shyness" (0~3): 害羞脸红/心事被看穿(若是讨厌的人油腻夸我，shyness填0，annoyance填2~3)\n'
    '   - "annoyance" (0~3): 烦躁/被冒犯/嫌弃油腻/被当工具人\n'
    '   - "curiosity" (0~3): 好奇/想细看/想探究新梗\n'
    "4. shade (6~16字): 复合微情绪染色词（如“被画成女仆的羞恼”、“酸中带甜的傲娇别扭”）。\n"
    "5. subtext (8~22字): 听出的弦外之音与潜台词。\n"
    "6. thought (12~32字): 第一人称真实内心OS。\n"
    '只输出单行 JSON：{"role":"peer_dyadic","topic_pull":0,'
    '"chord":{"joy":0,"hurt":0,"jealousy":0,"shyness":0,"annoyance":0,"curiosity":0},'
    '"shade":"平静旁听","subtext":"他们在聊自己的事","thought":"..."}'
)


class SubconsciousChordResult(FrozenValueObject):
    """Validated 6D emotional chord and pragmatic role from the subconscious probe."""

    role: str = "ambient_daily"
    topic_pull: int = 1
    joy: int = 0
    hurt: int = 0
    jealousy: int = 0
    shyness: int = 0
    annoyance: int = 0
    curiosity: int = 0
    shade: str = "平静"
    subtext: str = ""
    thought: str = ""


def _clamp_int(val: Any, lo: int, hi: int, default: int = 0) -> int:
    try:
        return max(lo, min(hi, int(val)))
    except Exception:
        return default


def parse_chord_json(raw_text: str) -> SubconsciousChordResult | None:
    """Parse raw LLM output into a validated SubconsciousChordResult."""
    match = JSON_EXTRACT_RE.search(raw_text)
    if not match:
        return None
    try:
        data: dict[str, Any] = json.loads(match.group(0))
    except Exception:
        return None
    raw_ch = data.get("chord")
    ch: dict[str, Any] = raw_ch if isinstance(raw_ch, dict) else {}
    role = str(data.get("role", "ambient_daily")).strip()
    if role not in ("direct_to_me", "about_me", "peer_dyadic", "ambient_daily", "noise"):
        role = "ambient_daily"
    return SubconsciousChordResult(
        role=role,
        topic_pull=_clamp_int(data.get("topic_pull", 1), 0, 3, 1),
        joy=_clamp_int(ch.get("joy", 0), 0, 3, 0),
        hurt=_clamp_int(ch.get("hurt", 0), 0, 3, 0),
        jealousy=_clamp_int(ch.get("jealousy", 0), -3, 3, 0),
        shyness=_clamp_int(ch.get("shyness", 0), 0, 3, 0),
        annoyance=_clamp_int(ch.get("annoyance", 0), 0, 3, 0),
        curiosity=_clamp_int(ch.get("curiosity", 0), 0, 3, 0),
        shade=str(data.get("shade", "平静")).strip()[:24] or "平静",
        subtext=str(data.get("subtext", "")).strip()[:48],
        thought=str(data.get("thought", "")).strip()[:64],
    )


def _clamp_f(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, round(val, 2)))


def _compute_chord_affect(
    aff: AffectiveVector,
    chord: SubconsciousChordResult,
    w_care: float,
    w_aver: float,
    speaker_aff: float,
) -> AffectiveVector:
    c_shy, c_ann = chord.shyness, chord.annoyance
    if (speaker_aff < 30.0 or aff.irritation >= 45.0) and c_shy > 0:
        c_ann = max(c_ann, c_shy + 1)
        c_shy = 0
    d_j = (
        8.5 * chord.jealousy * max(0.18, w_care)
        if chord.jealousy > 0
        else 5.0 * chord.jealousy * max(0.3, w_care)
    )
    d_i = 6.5 * c_ann * w_aver + 0.18 * max(0.0, d_j) - 2.0 * chord.joy * (0.4 + 0.6 * w_care)
    d_s = 5.5 * c_shy * (0.35 + 0.65 * w_care) + 0.15 * max(0.0, d_j) - 0.30 * max(0.0, d_i)
    d_v = (
        (4.8 * chord.joy - 6.0 * chord.hurt) * (0.5 + 0.6 * w_care)
        - 0.28 * max(0.0, d_j)
        - 0.25 * max(0.0, d_i)
    )
    new_j = _clamp_f(aff.jealousy * 0.85 + d_j * (1.0 - aff.jealousy / 120.0))
    new_i = _clamp_f(aff.irritation * 0.84 + d_i * (1.0 - aff.irritation / 120.0))
    new_s = _clamp_f(18.0 + (aff.shyness - 18.0) * 0.82 + d_s, 10.0, 100.0)
    new_v = _clamp_f(aff.valence + (62.0 - aff.valence) * 0.08 + d_v, -100.0, 100.0)
    new_e = _clamp_f(aff.energy + (circadian_energy_target() - aff.energy) * 0.14 - 1.2)
    return AffectiveVector(
        valence=new_v, energy=new_e, jealousy=new_j, shyness=new_s, irritation=new_i
    )


def _compute_chord_drives(
    drv: DriveState, new_aff: AffectiveVector, chord: SubconsciousChordResult, w_care: float
) -> DriveState:
    soothe = (
        min(16.0, drv.attachment * 0.20 * w_care)
        if (w_care >= 0.20 and chord.joy >= 1 and chord.jealousy <= 0)
        else -0.8
    )
    new_att = _clamp_f(drv.attachment - soothe + 1.8 * max(0, chord.jealousy), 18.0, 95.0)
    shy_factor = 1.0 - 0.25 * (new_aff.shyness / 100.0)
    new_j_drv = _clamp_f(new_aff.jealousy * (0.55 + 0.45 * (new_att / 100.0)) * shy_factor)
    cur_step = 4.5 * chord.curiosity - (2.0 if chord.curiosity == 0 else 0.0)
    new_cur = _clamp_f(drv.curiosity + cur_step)
    soc_d = 1.5 * chord.topic_pull + 0.06 * (new_aff.valence - 50.0) - 0.20 * new_aff.irritation
    soc_pull = (48.0 - drv.social_expression) * 0.10
    new_soc = _clamp_f(drv.social_expression + soc_pull + soc_d, 18.0, 92.0)
    return DriveState(
        curiosity=new_cur, attachment=new_att, jealousy_drive=new_j_drv, social_expression=new_soc
    )


def _format_spillover_thought(
    prev_thought: str, chord: SubconsciousChordResult, speaker_name: str
) -> str:
    has_strong = (
        abs(chord.jealousy) >= 1 or chord.hurt >= 1 or chord.annoyance >= 1 or chord.joy >= 2
    )
    if not has_strong and prev_thought:
        return prev_thought
    sub = f"（潜台词：{chord.subtext}）" if chord.subtext else ""
    return f"[源头:{speaker_name} · 🎨{chord.shade}] {chord.thought}{sub}"[:140]


def _evaluate_about_me_wake(
    percept: Percept, chord: SubconsciousChordResult, w_care: float, head: str,
    *, in_ambient_cooldown: bool, has_unseen: bool,
) -> AttentionDecision:
    if chord.jealousy > 0 and w_care < 0.22:
        return AttentionDecision(
            should_wake=False, salience_score=0.38, tier=0,
            reason=f"微酸不插嘴(w_care={w_care:.2f}) · {head}", has_unseen_media=has_unseen,
        )
    if in_ambient_cooldown and w_care < 0.95 and not (percept.is_called_by_name and chord.joy >= 2):
        return AttentionDecision(
            should_wake=False, salience_score=0.45, tier=0,
            reason=f"外围冷却攒心结 · {head}", has_unseen_media=has_unseen,
        )
    return AttentionDecision(
        should_wake=True, salience_score=0.78, tier=2,
        reason=f"关于我/醋意触发 · {head}", has_unseen_media=has_unseen,
    )


def evaluate_chord_wake_decision(
    percept: Percept, chord: SubconsciousChordResult, working: WorkingSnapshot, w_care: float,
    *, in_ambient_cooldown: bool = False, has_unseen: bool = False,
) -> AttentionDecision:
    """Determine wake decision from Goffman categorical role, chord, and homeostatic tank."""
    head = f"🧠 [{chord.shade}] {chord.thought or '潜意识感知'}"
    if chord.role == "direct_to_me":
        return AttentionDecision(
            should_wake=True, salience_score=0.92, tier=1,
            reason=f"直接对话 · {head}", has_unseen_media=has_unseen,
        )
    if chord.role in ("peer_dyadic", "noise") or chord.topic_pull == 0:
        return AttentionDecision(
            should_wake=False, salience_score=0.16, tier=0,
            reason=f"静默旁听 · {head}", has_unseen_media=has_unseen,
        )
    if chord.role == "about_me":
        return _evaluate_about_me_wake(
            percept, chord, w_care, head,
            in_ambient_cooldown=in_ambient_cooldown, has_unseen=has_unseen,
        )
    soc_ratio = working.drives.social_expression / 100.0
    chime = round((0.28 + 0.72 * w_care) * soc_ratio * (chord.topic_pull / 3.0), 2)
    wake = (not in_ambient_cooldown) and chime >= 0.34
    tag = "水箱共鸣接话" if wake else f"日常旁听(共鸣{chime}<0.34)"
    return AttentionDecision(
        should_wake=wake, salience_score=max(0.22, min(0.82, chime + 0.30)),
        tier=3 if wake else 0, reason=f"{tag} · {head}", has_unseen_media=has_unseen,
    )


def _resolve_speaker_aff_and_trust(
    uid: str, owner_qq: str, bond: SocialBondProfile | None
) -> tuple[float, float]:
    if owner_qq and uid == owner_qq:
        return 9999.0, 1.0
    return (bond.affinity_score, bond.trust_score) if bond is not None else (35.0, 0.80)


def apply_chord_tensor_to_snapshot(
    snapshot: WorkingSnapshot, chord: SubconsciousChordResult, percept: Percept,
    owner_qq: str, bond: SocialBondProfile | None = None, *, in_ambient_cooldown: bool = False,
) -> tuple[WorkingSnapshot, AttentionDecision]:
    """Apply 6D chord tensor to WorkingSnapshot and compute AttentionDecision."""
    w_care = compute_care_weight(percept.sender_id, owner_qq, bond)
    w_aver = compute_aversion_susceptibility(percept.sender_id, owner_qq, bond)
    s_aff, _ = _resolve_speaker_aff_and_trust(percept.sender_id, owner_qq, bond)
    new_aff = _compute_chord_affect(snapshot.affect, chord, w_care, w_aver, s_aff)
    new_drv = _compute_chord_drives(snapshot.drives, new_aff, chord, w_care)
    spill = _format_spillover_thought(
        snapshot.inner_thought, chord, percept.sender_name or percept.sender_id
    )
    updated = snapshot.model_copy(
        update={"affect": new_aff, "drives": new_drv, "inner_thought": spill}
    )
    unseen = any(not m.description for m in percept.media)
    dec = evaluate_chord_wake_decision(
        percept, chord, updated, w_care, in_ambient_cooldown=in_ambient_cooldown, has_unseen=unseen
    )
    return updated, dec


class SubconsciousChordProbe:
    """Lightweight subconscious LLM probe for 6D emotional chord and pragmatic role."""

    def __init__(self, llm: ILlmGateway, owner_qq: str = "") -> None:
        self._llm, self._owner_qq = llm, owner_qq

    async def appraise(
        self, percept: Percept, recent_lines: tuple[str, ...],
        bond: SocialBondProfile | None = None, timeout_s: float = 2.8,
    ) -> SubconsciousChordResult | None:
        """Run a fast subconscious JSON probe with timeout protection."""
        uid = percept.sender_id
        aff, trust = _resolve_speaker_aff_and_trust(uid, self._owner_qq, bond)
        rel = (
            "唯一主人(至高依恋)" if (self._owner_qq and uid == self._owner_qq)
            else (f"亲近好友(好感{aff:.0f})" if aff >= 52.0 else f"普通群友(好感{aff:.0f})")
        )
        ctx_str = "\n".join(recent_lines[-6:]) if recent_lines else "（无）"
        u_prompt = (
            f"【发言人】{percept.sender_name}(QQ:{uid}) -> {rel}, 信任度{trust:.2f}\n"
            f"【近期上下文】\n{ctx_str}\n"
            f"【最新消息】\n{percept.sender_name}(QQ:{uid}): {percept.text[:140]}"
        )
        try:
            msgs = [
                {"role": "system", "content": CHORD_PROBE_SYS},
                {"role": "user", "content": u_prompt},
            ]
            ck = f"subconscious:{percept.chat_key}"
            resp = await asyncio.wait_for(
                self._llm.complete(msgs, temperature=0.1, max_tokens=160, chat_key=ck),
                timeout=timeout_s,
            )
            choices = resp.get("choices", [])
            raw = str(choices[0].get("message", {}).get("content", "")) if choices else ""
            return parse_chord_json(raw)
        except Exception:
            return None
