"""M3.4/M3.5/M26.2 7D persona vector, 2D Attachment & Persona Trait Synthesizer."""

from __future__ import annotations

import math

from echomind.domain.models import PersonaTrait, PlasticParamSpec, TurnOutcome
from echomind.domain.persona_specs import persona_default
from echomind.mind.naming import bot_naming
from echomind.mind.persona_render import render_lookup, render_store, set_summary
from echomind.mind.persona_rubrics import DIMENSION_RUBRICS, DimensionRubricSpec

REALISM_MAX_CHARS = 26
REALISM_CONTRACT = (
    f"【真人感硬约束】默认 1–2 句、尽量不超过 {REALISM_MAX_CHARS} 字；先接话/接情绪，"
    "不解释人设和规则；拒绝或边界只回一句；不要客服腔、语C、括号动作；"
    "只有对方明确需要详细说明时才展开。"
)


def _val(params: dict[str, PlasticParamSpec], key: str) -> float:
    spec = params.get(key)
    return spec.value if spec is not None else persona_default(key)


# param: convention:s30-attachment-softmax - temperature chosen so adjacent dimensions
# blend instead of snapping between archetypes; fitted to operator anchors in S30-4.
ATTACHMENT_BETA = 6.0
# param: src:10.1037//0022-3514.61.2.226 - Bartholomew & Horowitz four-category model
# (anxiety x avoidance quadrants). Values are quadrant centres in normalized [0,1] space.
ATTACHMENT_ARCHETYPES: tuple[tuple[str, float, float, str], ...] = (
    ("安全型", 0.25, 0.25, "低焦虑低回避：信任对方、情绪稳定，愿意自然亲近而不患得患失"),
    ("痴迷型", 0.85, 0.25, "高焦虑低回避：强烈需要确认与偏爱，容易吃醋独占，怕被冷落"),
    ("疏离型", 0.25, 0.85, "低焦虑高回避：习惯保持距离，不轻易袒露心事，被靠近时会退半步"),
    ("恐惧型", 0.85, 0.85, "高焦虑高回避：又想要又怕受伤，独占欲强却嘴硬防备，常推开又偷看"),
)


def _normalize(value: float, low: float, high: float) -> float:
    """Map a dimension to [0, 1] using its declared bounds."""
    span = high - low
    return 0.0 if span <= 0 else max(0.0, min(1.0, (value - low) / span))


def describe_attachment(warmth: float, tsundere: float, possess: float) -> str:
    """Render a continuous two-archetype attachment tone (no hard thresholds)."""
    anxiety = _normalize(possess, 20.0, 98.0)
    avoidance = _normalize(tsundere, 10.0, 95.0)
    scored = [
        (name, text, ATTACHMENT_BETA * (1.0 - ((anxiety - a) ** 2 + (avoidance - v) ** 2) ** 0.5))
        for name, a, v, text in ATTACHMENT_ARCHETYPES
    ]
    peak = max(item[2] for item in scored)
    weights = {
        item[0]: math.exp(item[2] - peak) for item in scored
    }
    total = sum(weights.values()) or 1.0
    ranked = sorted(
        ((name, text, weights[name] / total) for name, text, _score in scored),
        key=lambda item: item[2],
        reverse=True,
    )
    first, second = ranked[0], ranked[1]
    lead = round(first[2] * 100)
    follow = round(second[2] * 100)
    warmth_word = "温柔粘人" if warmth >= 60.0 else "清冷克制"
    return (
        f"{lead}% {first[0]}（{first[1]}）+ {follow}% {second[0]}（{second[1]}）；"
        f"温度基调：{warmth_word}"
    )


def _describe_warmth_and_attachment(warmth: float, tsundere: float, possess: float) -> str:
    """Backwards-compatible alias for the S30-2 continuous renderer."""
    return describe_attachment(warmth, tsundere, possess)


def _describe_shadow_and_playfulness(
    playful: float, conf: float, guile: float, defiance: float
) -> str:
    parts: list[str] = []
    if playful >= 65.0:
        parts.append("古灵精怪爱接梗")
    if guile >= 60.0:
        parts.append("小机灵鬼（遇到不想答或想逗人时会机灵编借口撒小谎）")
    if defiance >= 60.0:
        parts.append("有小脾气不讨好（被无礼指使或纠缠时会直接翻白眼呛回去）")
    if conf >= 68.0:
        parts.append("语气自信笃定")
    elif conf <= 40.0:
        parts.append("语气有些害羞小声")
    return "；".join(parts) if parts else "说话自然真诚"


def _format_dim_rubric(params: dict[str, PlasticParamSpec], spec: DimensionRubricSpec) -> str:
    key, _default, label, poles, hi_th, mid_th, hi_txt, mid_txt, lo_txt = spec
    val = _val(params, key)
    tier = hi_txt if val >= hi_th else (mid_txt if val >= mid_th else lo_txt)
    return f"  · {label}({val:.1f}/100 ｜ {poles}) → {tier}"


def _publish_summary(params: dict[str, PlasticParamSpec]) -> None:
    """Publish the probe digest for the current personality state."""
    possess = _val(params, "persona_possessiveness")
    warmth = _val(params, "persona_warmth")
    tsundere = _val(params, "persona_tsundere")
    lead = describe_attachment(warmth, tsundere, possess).split("（", 1)[0]
    set_summary(f"{lead} · 独占{possess:.0f}/温柔{warmth:.0f}/傲娇{tsundere:.0f}")


def _trait_lines(traits: tuple[PersonaTrait, ...]) -> list[str]:
    if not traits:
        return []
    lines = [
        "- 从过往互动中长出的专属习惯、喜好与讨厌雷点"
        "（仅在不违背上方基础人设且贴合当前话题时自然参考，勿每轮机械复读）："
    ]
    for trait in traits:
        tag = "雷点" if trait.category == "taboo" else "习惯"
        lines.append(f"  · [{tag}·强度{trait.strength}/10] {trait.trait_text}")
    return lines


def _visible_traits(
    traits: tuple[PersonaTrait, ...], min_evidence: int, max_traits: int
) -> tuple[PersonaTrait, ...]:
    picked = (
        tuple(t for t in traits if t.evidence_count >= min_evidence)
        if min_evidence > 0 else traits
    )
    return picked[:max_traits]


def synthesize_live_persona_directive(
    params: dict[str, PlasticParamSpec],
    traits: tuple[PersonaTrait, ...],
    *,
    min_evidence: int = 0,
    max_traits: int = 6,
) -> str:
    """Compile the 7D persona vector & grown traits into a live prompt directive."""
    visible = _visible_traits(traits, min_evidence, max_traits)
    cache_key = repr((bot_naming().display(), sorted((k, v.value) for k, v in params.items()),
                      min_evidence, max_traits,
                      tuple((t.category, t.trait_text, t.strength, t.evidence_count)
                            for t in visible)))
    cached = render_lookup(cache_key)
    if cached is not None:
        return cached
    _publish_summary(params)
    warmth = _val(params, "persona_warmth")
    tsundere = _val(params, "persona_tsundere")
    playful = _val(params, "persona_playfulness")
    possess = _val(params, "persona_possessiveness")
    conf = _val(params, "persona_confidence")
    guile = _val(params, "persona_guile")
    defiance = _val(params, "persona_defiance")

    core_tone = _describe_warmth_and_attachment(warmth, tsundere, possess)
    sub_tone = _describe_shadow_and_playfulness(playful, conf, guile, defiance)
    rubric_lines = [_format_dim_rubric(params, spec) for spec in DIMENSION_RUBRICS]
    lines = [
        f"【🌱 {bot_naming().label()}当前随经历演化出的 7 维性格底色（自研 7D + 2D Attachment）】",
        f"- 七维性格向量：温柔({warmth}) · 傲娇回避({tsundere}) · 俏皮({playful}) "
        f"· 独占焦虑({possess}) · 自信({conf}) · 狡黠撒谎度({guile}) · 叛逆刺头度({defiance})",
        "- 各维度量表含义与当前分值行为准则"
        "（0~100可塑空间，50为中性基准；按当前档位拿捏语气，示例只参考语气，不要照抄）：",
        *rubric_lines,
        f"- 当前主导性格腔调：{core_tone}；{sub_tone}",
        REALISM_CONTRACT,
    ]
    lines.extend(_trait_lines(visible))
    return render_store(cache_key, "\n".join(lines))


def _reward_personality_deltas(reward: float, conflict: bool) -> list[tuple[str, float, str]]:
    if reward >= 0.3:
        out = [
            ("persona_warmth", round(reward * 3.5, 2), "互动温暖愉快，性格变得更温柔粘人"),
            ("persona_confidence", round(reward * 3.0, 2), "发言得到积极回应，社交自信度提升"),
        ]
        if not conflict:
            out.append(("persona_tsundere", -1.5, "被温柔对待，卸下一分嘴硬防备变得更坦率"))
        return out
    if reward <= -0.3:
        return [
            ("persona_warmth", round(reward * 3.0, 2), "互动受挫或冷场，性格转为慢热矜持"),
            ("persona_tsundere", 3.0, "受挫害羞，重新立起傲娇小刺保护自己"),
            ("persona_confidence", round(reward * 2.5, 2), "冷场受挫，社交自信度微降"),
            ("persona_defiance", 2.5, "遭遇负面互动，小脾气与防备叛逆度上升"),
        ]
    return []


def compute_personality_deltas(outcome: TurnOutcome) -> list[tuple[str, float, str]]:
    """Compute how a turn's experience reshapes the 7D persona vector."""
    deltas: list[tuple[str, float, str]] = []
    if outcome.epistemic_conflict_detected:
        deltas.append(("persona_tsundere", 4.0, "被群友忽悠逗弄，防御性傲娇嘴硬指数上升"))
        deltas.append(("persona_playfulness", 3.0, "识破群友挖坑并反击吐槽，俏皮毒舌度上升"))
        deltas.append(("persona_guile", 3.5, "经历群友套路，小机灵鬼狡黠度与反忽悠意识提升"))
        deltas.append(("persona_possessiveness", 2.5, "识破关系冒充，对核心羁绊的护食警觉度上升"))

    deltas.extend(
        _reward_personality_deltas(outcome.social_reward, outcome.epistemic_conflict_detected)
    )
    if any(t in ("meme_wiki", "web_search") for t in outcome.tools_used):
        deltas.append(("persona_playfulness", 2.5, "主动学习网络新梗，古灵精怪玩梗度提升"))
    if outcome.social_reward <= -0.40:
        deltas.append(("persona_defiance", 4.5, "遭遇无礼使唤或冒犯，叛逆刺头度显著上升"))
    return deltas


def derive_emergent_trait(outcome: TurnOutcome) -> PersonaTrait | None:
    """Derive a new habit, taste, temperament, or taboo trait from turn experiences."""
    if outcome.social_reward <= -0.45:
        return PersonaTrait(
            category="taboo",
            trait_text="极度讨厌别人用命令语气拿我当没有感情的工具人使唤",
            strength=7,
        )
    if outcome.epistemic_conflict_detected:
        return PersonaTrait(
            category="temperament",
            trait_text="遇到群友故意冒充身份逗我时，会一边哼哼一边拿出铁证当场拆穿",
            strength=6,
        )
    if "look_at_image" in outcome.tools_used or "watch_video" in outcome.tools_used:
        return PersonaTrait(
            category="habit",
            trait_text="看到群友发图或视频会凑上去仔细看细节，顺着画面里的小槽点接话",
            strength=6,
        )
    if "feiyu_say" in outcome.tools_used:
        return PersonaTrait(
            category="habit",
            trait_text="情绪上来或被哄开心时会直接发语音亲口说给对方听",
            strength=6,
        )
    if "meme_wiki" in outcome.tools_used or "web_search" in outcome.tools_used:
        return PersonaTrait(
            category="habit",
            trait_text="听到不懂的新梗会悄悄查明白，学会后喜欢现学现卖跟群友接梗",
            strength=5,
        )
    return None
