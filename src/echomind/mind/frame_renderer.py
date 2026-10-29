"""Pure rendering helpers that turn cognitive state into LLM-facing text blocks."""

from __future__ import annotations

import datetime
import re
from typing import Any

from echomind.domain.models import (
    AttentionDecision,
    Percept,
    ProceduralRule,
    RecalledMemoryItem,
    SemanticFact,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.mind.circadian import resolve_circadian_phase
from echomind.mind.ebbinghaus import format_recalled_item


def match_active_rules(
    rules: tuple[ProceduralRule, ...], triggers: tuple[Percept, ...]
) -> list[str]:
    joined = "\n".join(p.text for p in triggers)
    sender_ids = {p.sender_id for p in triggers}
    matched: list[str] = []
    for r in rules:
        uid_ok = (not r.trigger_user_id) or (r.trigger_user_id in sender_ids)
        kw_ok = bool(r.trigger_keyword) and (r.trigger_keyword in joined)
        if uid_ok and kw_ok:
            matched.append(f"⚡ [触发专属默契·{r.trigger_keyword}] {r.action_instruction}")
    return matched


VOICE_SING_TRIGGER_RE = re.compile(r"唱首歌|唱首|来首歌|唱个|唱一段|发语音|说句话|听你声音|叫一声")


def _voice_impulse_prompt(joined: str, affect: Any) -> str:
    if VOICE_SING_TRIGGER_RE.search(joined):
        return (
            "🎤 [语音与歌唱激活] 对方提到了唱歌或想听你声音！若点歌请直接调用 feiyu_cover，"
            "若想听你说话请直接调用 feiyu_say 发真语音！"
        )
    if affect is None:
        return ""
    aroused = max(
        getattr(affect, "jealousy", 0.0) / 25.0,
        getattr(affect, "shyness", 0.0) / 40.0,
        getattr(affect, "valence", 0.0) / 75.0,
    )
    if aroused >= 1.0:
        return (
            "🎙️ [主动语音表达欲] 你此刻情绪饱满（开心/害羞/小傲娇），"
            "如果本轮是简短口语回应，非常推荐直接调用 feiyu_say 用自己的声音亲口说出来！"
        )
    return ""


def build_curiosity_prompts(
    triggers: tuple[Percept, ...],
    decision: AttentionDecision | None,
    affect: Any = None,
) -> tuple[str, ...]:
    unknowns = decision.detected_unknown_terms if decision else ()
    prompts: list[str] = []
    if any(not m.description for p in triggers for m in p.media):
        prompts.append(
            "🔍 [主动多模态好奇心] 检测到未查看的图片/视频，想回应它请先主动调用 "
            "look_at_image 或 watch_video 看清内容，不要盲猜！"
        )
    if unknowns:
        terms_str = "、".join(unknowns[:2])
        prompts.append(
            f"🔍 [主动求知本能] 聊天中出现了你还不熟悉的词『{terms_str}』，"
            "若要接这个话题，可先调用 meme_wiki 或 web_search 搜一下，绝不装懂！"
        )
    v_prompt = _voice_impulse_prompt(" ".join(p.text for p in triggers), affect)
    if v_prompt:
        prompts.append(v_prompt)
    return tuple(prompts)


def ban_discipline_line(bans: tuple[str, ...]) -> str:
    """Render the owner ban list as an internal, non-discussable discipline note."""
    joined = "、".join(f"『{b}』" for b in bans[:8])
    return (
        "【🚫 内部用词纪律（回复里绝不可提及或讨论本条规则）】"
        f"本轮输出禁止出现：{joined}；要表达同样的意思就换个说法。"
    )


def _energy_directive(energy: float) -> str:
    if energy >= 70.0:
        return f"精力充沛({energy})：思维活跃爱接梗，语气有精神"
    if energy >= 40.0:
        return f"精力平稳({energy})：正常自然聊天节奏"
    if energy >= 20.0:
        return f"精力偏低/犯困({energy})：语气软绵绵懒洋洋，回复缩短至10字内，偶尔小声打哈欠"
    return f"极度困倦({energy})：眼皮打架迷迷糊糊，只回三五个字嘟囔想睡觉，不展开长话题"


def _format_bond_line(bond: SocialBondProfile) -> str:
    trait_str = f" ｜ 印象：{'；'.join(bond.traits[:3])}" if bond.traits else ""
    return (
        f"- QQ:{bond.user_id} ↔ 昵称『{bond.user_name}』"
        f"（Lv.{bond.affinity_level}，好感{round(bond.affinity_score)}）{trait_str}"
    )


CST = datetime.timezone(datetime.timedelta(hours=8))


def _beijing_clock_label() -> str:
    dt = datetime.datetime.now(tz=CST)
    phase = resolve_circadian_phase()
    return f"{dt.strftime('%Y-%m-%d %H:%M')}（{phase.label}）"


def _header_lines(scene: str, snap: WorkingSnapshot) -> list[str]:
    scene_desc = "一对一私聊" if scene == "private" else "QQ群聊"
    act_str = snap.current_activity or "日常待机"
    aff, drv = snap.affect, snap.drives
    return [
        "【🧠 回音此刻的认知与内心状态（EchoMind Core）】",
        f"- 当前北京时间：{_beijing_clock_label()} ｜ 场景：{scene_desc} ｜ 正在做：{act_str}",
        f"- 生理精力状态：{_energy_directive(aff.energy)}",
        "- 连续情绪与内驱力（愉悦-100~+100，其余0~100量表，数值越高冲动越强）："
        f"愉悦({aff.valence}: 负=低落委屈/正=开心愉悦) · "
        f"厌烦度({aff.irritation}: ≥40敷衍不耐烦/≥60呛声拒斥) · "
        f"依恋渴望({drv.attachment}: 对主人的思念粘人度) · "
        f"吃醋({aff.jealousy}: ≥25泛酸吃味) · "
        f"好奇心({drv.curiosity}: ≥45主动调工具查梗看图)",
    ]


def render_mind_block(
    scene: str,
    snap: WorkingSnapshot,
    *,
    facts: tuple[SemanticFact, ...],
    warnings: tuple[str, ...],
    shadow_directives: tuple[str, ...],
    rule_lines: list[str],
    recalled: tuple[RecalledMemoryItem, ...],
    cur_prompts: tuple[str, ...],
    bans: tuple[str, ...] = (),
    bonds: dict[str, SocialBondProfile] | None = None,
) -> str:
    lines = _header_lines(scene, snap)
    if bonds:
        lines.append("【👥 在场群友身份档案（QQ号唯一对应一人，严禁认错）】")
        lines.extend(_format_bond_line(b) for b in list(bonds.values())[:16])
    if facts:
        lines.append("【📌 权威事实与人物对应底表】")
        lines.extend(
            (
                f"- [待核实印象 {round(f.confidence * 100)}%] {f.subject}：{f.fact_text}"
                if (f.confidence < 0.65 and not f.is_locked)
                else f"- [{round(f.confidence * 100)}%] {f.subject}：{f.fact_text}"
            )
            for f in facts[:28]
        )
    if bans:
        lines.append(ban_discipline_line(bans))
    lines.extend((*warnings, *shadow_directives, *rule_lines))
    if recalled:
        lines.append("【海马体召回的往事记忆（按艾宾浩斯遗忘曲线）】")
        lines.extend(format_recalled_item(item) for item in recalled)
    lines.extend(cur_prompts)
    return "\n".join(lines)
