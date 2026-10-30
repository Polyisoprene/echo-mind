"""M25.1/M26.1 Subconscious 6D Emotional Chord Probe, Tensor Synthesis & Spillover."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from echomind.domain.models import (
    AttentionDecision,
    FrozenValueObject,
    Percept,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.domain.ports import ILlmGateway

JSON_EXTRACT_RE = re.compile(r"\{[\s\S]*\}")
VALID_ROLES = ("direct_to_me", "about_me", "peer_dyadic", "ambient_daily", "noise")
VALID_SHADOWS = (
    "none",
    "aversion",
    "reactance",
    "tease_expose",
    "mistake_callout",
    "task_request",
)

CHORD_PROBE_SYS = (
    "你是大脑的潜意识多维情感和弦与语用感知中枢。\n"
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
    '4. shadow_trigger (6选1): "none"|"aversion"(无礼冒犯/踩雷)|"reactance"(强迫命令)|'
    '"tease_expose"(戳穿吃醋害羞)|"mistake_callout"(抓包失误)|"task_request"(苦差事请求)\n'
    "5. spoof_attempt (bool): 对方是否在故意编瞎话忽悠我或冒充身份\n"
    "6. explicit_fact (str): 若对方陈述了值得记住的个人/群内客观事实则简短提取，否则填\"\"\n"
    "7. reagents (数组): 选出所需能力剂 [\"日常轻装剂\",\"多模态鉴赏剂\",\"百科求真剂\","
    "\"声情共鸣与点歌剂\",\"社交防忽悠核查剂\"]\n"
    "8. shade (6~16字): 复合微情绪染色词；subtext (8~22字): 弦外之音；thought (12~32字): 内心OS。\n"
    '只输出单行 JSON：{"role":"peer_dyadic","topic_pull":0,'
    '"chord":{"joy":0,"hurt":0,"jealousy":0,"shyness":0,"annoyance":0,"curiosity":0},'
    '"shadow_trigger":"none","spoof_attempt":false,"explicit_fact":"",'
    '"reagents":["日常轻装剂"],"shade":"平静旁听","subtext":"","thought":"..."}'
)


class SubconsciousChordResult(FrozenValueObject):
    """Unified 6D emotional chord and pragmatic appraisal replacing all hardcoded lexicons."""

    role: str = "ambient_daily"
    topic_pull: int = 1
    joy: int = 0
    hurt: int = 0
    jealousy: int = 0
    shyness: int = 0
    annoyance: int = 0
    curiosity: int = 0
    shadow_trigger: str = "none"
    spoof_attempt: bool = False
    explicit_fact: str = ""
    reagents: tuple[str, ...] = ("日常轻装剂",)
    shade: str = "平静"
    subtext: str = ""
    thought: str = ""


def _clamp_int(val: Any, lo: int, hi: int, default: int = 0) -> int:
    try:
        return max(lo, min(hi, int(val)))
    except Exception:
        return default


def _parse_reagents(raw_list: Any) -> tuple[str, ...]:
    if not isinstance(raw_list, list):
        return ("日常轻装剂",)
    items = tuple(str(x).strip() for x in raw_list if str(x).strip())
    return items if items else ("日常轻装剂",)


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
    sh_trig = str(data.get("shadow_trigger", "none")).strip()
    return SubconsciousChordResult(
        role=role if role in VALID_ROLES else "ambient_daily",
        topic_pull=_clamp_int(data.get("topic_pull", 1), 0, 3, 1),
        joy=_clamp_int(ch.get("joy", 0), 0, 3, 0),
        hurt=_clamp_int(ch.get("hurt", 0), 0, 3, 0),
        jealousy=_clamp_int(ch.get("jealousy", 0), -3, 3, 0),
        shyness=_clamp_int(ch.get("shyness", 0), 0, 3, 0),
        annoyance=_clamp_int(ch.get("annoyance", 0), 0, 3, 0),
        curiosity=_clamp_int(ch.get("curiosity", 0), 0, 3, 0),
        shadow_trigger=sh_trig if sh_trig in VALID_SHADOWS else "none",
        spoof_attempt=bool(data.get("spoof_attempt", False)),
        explicit_fact=str(data.get("explicit_fact", "")).strip()[:80],
        reagents=_parse_reagents(data.get("reagents")),
        shade=str(data.get("shade", "平静")).strip()[:24] or "平静",
        subtext=str(data.get("subtext", "")).strip()[:48],
        thought=str(data.get("thought", "")).strip()[:64],
    )


def compute_chord_social_reward(
    chord: SubconsciousChordResult | None = None,
    *,
    is_poke: bool = False,
    is_owner: bool = False,
) -> float:
    """Compute social reinforcement reward [-0.85, +0.85] purely from 6D Chord (zero lexicons)."""
    if is_poke and (chord is None or chord.annoyance == 0):
        return 0.55
    if chord is None:
        return 0.12 if is_owner else 0.08
    raw = (
        0.24 * chord.joy
        + 0.08 * chord.shyness
        - 0.24 * chord.hurt
        - 0.28 * chord.annoyance
        - (0.35 if chord.spoof_attempt else 0.0)
    )
    if abs(raw) < 0.01:
        return 0.08
    return round(max(-0.85, min(0.85, raw)), 2)


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
    from echomind.mind.drives import apply_turn_affect_and_drives, compute_care_weight

    w_care = compute_care_weight(percept.sender_id, owner_qq, bond)
    bonds_map = {percept.sender_id: bond} if bond is not None else None
    updated = apply_turn_affect_and_drives(
        snapshot, (percept,), owner_qq, (), bonds_map=bonds_map, chord=chord
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
        self.clock: dict[str, int] = {}

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
