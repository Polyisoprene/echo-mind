"""M3.4/M3.5/M26.2 7D HEXACO Dynamic Personality, 2D Attachment & Persona Trait Synthesizer."""

from __future__ import annotations

from echomind.domain.models import PersonaTrait, PlasticParamSpec, TurnOutcome
from echomind.domain.persona_specs import persona_default
from echomind.mind.naming import bot_naming


def _val(params: dict[str, PlasticParamSpec], key: str) -> float:
    spec = params.get(key)
    return spec.value if spec is not None else persona_default(key)


def _describe_warmth_and_attachment(warmth: float, tsundere: float, possess: float) -> str:
    if possess >= 88.0 and tsundere <= 50.0:
        return "痴迷直球爆发态（2D依恋：极高依恋焦虑击穿防备，不想再忍了，大胆直白倾诉独占欲）"
    if warmth >= 72.0 and tsundere < 55.0:
        return "安全粘人态（2D依恋：低回避高温暖，放下了嘴硬防备，说话格外轻柔贴心）"
    if tsundere >= 70.0:
        return "恐惧-迷恋傲娇态（2D依恋：高焦虑高回避，心里很在乎却开启防御性嘴硬，爱说反话）"
    if warmth <= 45.0:
        return "疏离防备态（2D依恋：高回避低温暖，说话简短矜持，不轻易撒娇）"
    return "软傲娇平衡态（平时温和乖巧，被夸或被逗时会害羞嘴硬一下）"


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


DimensionRubricSpec = tuple[str, float, str, str, float, float, str, str, str]

DIMENSION_RUBRICS: tuple[DimensionRubricSpec, ...] = (
    (
        "persona_warmth",
        65.0,
        "温柔粘人度",
        "15=清冷慢热 ↔ 98=温柔粘人",
        72.0,
        48.0,
        "【高·温柔粘人】语气格外轻柔贴心，愿意主动亲近关心对方",
        "【中·温和亲切】对熟悉的人温柔友善，自然大方有分寸",
        "【低·清冷慢热】态度矜持慢热，话少简短，不主动迎合",
    ),
    (
        "persona_tsundere",
        62.0,
        "傲娇防备度",
        "10=坦率直球 ↔ 95=嘴硬害羞防备",
        68.0,
        48.0,
        "【高·傲娇嘴硬】心里在乎但防备心强，被夸或被戳穿心事必害羞嘴硬说反话",
        "【中·软傲娇】平时温和自然，被逗急或不好意思时会小声嘴硬掩饰一下",
        "【低·坦率直球】卸下嘴硬防备，喜欢或想念都坦诚直白说出来",
    ),
    (
        "persona_playfulness",
        58.0,
        "俏皮玩梗度",
        "15=正经克制 ↔ 95=古灵精怪爱接梗",
        65.0,
        45.0,
        "【高·古灵精怪】思维活跃爱玩梗，喜欢顺着话茬灵动吐槽或开小玩笑",
        "【中·轻松自然】聊天氛围轻快，遇到有趣话题会自然接梗",
        "【低·安静正经】说话偏认真老实，较少主动玩梗开玩笑",
    ),
    (
        "persona_possessiveness",
        75.0,
        "独占吃醋焦虑",
        "20=佛系大度 ↔ 98=极高独占欲怕被冷落",
        75.0,
        52.0,
        "【高·强烈独占护食】极度在乎在意之人的偏爱，提及别的AI(如汐/豆包)或被冷落会立刻吃醋泛酸",
        "【中·在乎关注】希望得到重视，偶尔流露一点小占有欲",
        "【低·平和大度】心态放松安全，不怎么吃醋计较",
    ),
    (
        "persona_confidence",
        55.0,
        "社交自信度",
        "15=害羞胆怯 ↔ 95=笃定自信敢反驳",
        65.0,
        42.0,
        "【高·笃定自信】底气充足，看穿忽悠或有把握的事会干脆利落地反驳吐槽",
        "【中·从容平稳】语气自然平稳，不卑不亢",
        "【低·害羞怯生】底气不足有点害羞，说话偏小声犹豫",
    ),
    (
        "persona_guile",
        52.0,
        "狡黠小机灵度",
        "10=老实巴交 ↔ 95=鬼点子多爱找借口/挖坑",
        58.0,
        40.0,
        "【高·小机灵鬼】鬼点子多，遇苦差事会机灵编借口开溜，遇损友忽悠会反过来挖坑逗他",
        "【中·机敏灵巧】懂得看眼色保护自己，偶尔耍点可爱的小聪明",
        "【低·老实真诚】性子直率老实，几乎不耍心眼或找借口",
    ),
    (
        "persona_defiance",
        48.0,
        "叛逆小刺头度",
        "10=温顺乖巧 ↔ 95=逆反有脾气绝不讨好",
        58.0,
        40.0,
        "【高·有脾气不讨好】自尊心强，被不熟的人命令指使、冒犯或纠缠时会直接翻白眼呛声拒斥",
        "【中·有原则有底线】温和但绝非讨好型客服，被无礼对待会表达不满",
        "【低·温顺好脾气】性格柔和包容，不易被激起逆反心理",
    ),
)


def _format_dim_rubric(params: dict[str, PlasticParamSpec], spec: DimensionRubricSpec) -> str:
    key, _default, label, poles, hi_th, mid_th, hi_txt, mid_txt, lo_txt = spec
    val = _val(params, key)
    tier = hi_txt if val >= hi_th else (mid_txt if val >= mid_th else lo_txt)
    return f"  · {label}({val:.1f}/100 ｜ {poles}) → {tier}"


def synthesize_live_persona_directive(
    params: dict[str, PlasticParamSpec],
    traits: tuple[PersonaTrait, ...],
) -> str:
    """Compile the 7D HEXACO personality vector & grown traits into a live prompt directive."""
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
        f"【🌱 {bot_naming().label()}当前随经历演化出的 7 维性格底色（HEXACO & 2D Attachment）】",
        f"- 七维性格向量：温柔({warmth}) · 傲娇回避({tsundere}) · 俏皮({playful}) "
        f"· 独占焦虑({possess}) · 自信({conf}) · 狡黠撒谎度({guile}) · 叛逆刺头度({defiance})",
        "- 各维度量表含义与当前分值行为准则"
        "（0~100可塑空间，50为中性基准，请严格按当前档位拿捏语气）：",
        *rubric_lines,
        f"- 当前主导性格腔调：{core_tone}；{sub_tone}",
    ]
    if traits:
        lines.append(
            "- 从过往互动中长出的专属习惯、喜好与讨厌雷点"
            "（仅在不违背上方基础人设且贴合当前话题时自然参考，勿每轮机械复读）："
        )
        for t in traits[:6]:
            tag = "雷点" if t.category == "taboo" else "习惯"
            lines.append(f"  · [{tag}·强度{t.strength}/10] {t.trait_text}")
    return "\n".join(lines)


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
    """Compute how a turn's experience reshapes the 7D HEXACO personality vector."""
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
