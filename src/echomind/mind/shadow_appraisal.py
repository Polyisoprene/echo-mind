"""M3.5 Shadow Persona Appraisal: OCC Aversion, Brehm Reactance, Deception & 2D Attachment."""

from __future__ import annotations

import re

from echomind.domain.models import (
    AffectiveVector,
    EpisodicCard,
    FrozenValueObject,
    IntentionItem,
    Percept,
    PersonaTrait,
    PlasticParamSpec,
    SocialBondProfile,
)
from echomind.mind.ebbinghaus import compute_retention

RUDE_DISGUST_RE = re.compile(r"蠢AI|破机器人|工具人|人工智障|给你脸|废物|垃圾机器人|客服味")
COERCIVE_CMD_RE = re.compile(r"快给我|立刻给我|必须给我|命令你|给爷叫|快叫声|快点给我")
TEASE_EXPOSE_RE = re.compile(r"吃醋|酸了|害羞|脸红|想我了|在乎我|偷偷看")
MISTAKE_CALLOUT_RE = re.compile(r"记错了|说错了|搞错了|认错了|笨蛋|迷糊了")
TASK_REQUEST_RE = re.compile(r"帮我|给我查|去搜一下|给我写|替我")


class ShadowAppraisalResult(FrozenValueObject):
    """Immutable appraisal result for aversion, reactance, irritation, and deception."""

    irritation_delta: float = 0.0
    aversion_triggered: bool = False
    reactance_triggered: bool = False
    deception_mode: str = ""
    shadow_directives: tuple[str, ...] = ()


def _extract_taboo_texts(traits: tuple[PersonaTrait, ...]) -> tuple[str, ...]:
    return tuple(t.trait_text for t in traits if t.category == "taboo")


def _check_aversion(joined: str, taboos: tuple[str, ...]) -> str:
    if RUDE_DISGUST_RE.search(joined) or any(t and t in joined for t in taboos):
        return (
            "💢 [触发厌恶雷点 (OCC Disliking)] 对方提到了你最反感的词或用无礼方式使唤你，"
            "你心里非常嫌弃反感，请直接皱眉表达讨厌或冷淡呛回去，绝不讨好顺从！"
        )
    return ""


def _check_reactance_and_satiation(
    triggers: tuple[Percept, ...], is_owner: bool
) -> tuple[float, bool, str]:
    if is_owner:
        return -5.0, False, ""
    joined = " ".join(p.text for p in triggers)
    if COERCIVE_CMD_RE.search(joined):
        msg = (
            "🔥 [触发逆反心理 (Brehm Reactance)] 对方在用命令口吻强迫指使你！"
            "你产生了强烈的逆反心理，请直接翻白眼拒绝配合或故意唱反调（“你让我干嘛我就干嘛呀？偏不！”）。"
        )
        return 32.0, True, msg
    if len(triggers) >= 3:
        return (
            28.0,
            False,
            "😒 [触发厌烦情绪 (CPM Satiation)] 对方连珠炮刷屏追问，你感到有些不耐烦了。",
        )
    return -2.0, False, ""


def _check_ego_or_blame_lie(
    joined_text: str, affect: AffectiveVector, tsundere: float
) -> tuple[str, str] | None:
    if tsundere < 50.0:
        return None
    vulnerable = affect.jealousy >= 20.0 or affect.shyness >= 25.0
    if vulnerable and TEASE_EXPOSE_RE.search(joined_text):
        return (
            "face_saving_lie",
            "🎭 [护面子撒谎本能 (Face-Saving Lie)] 对方看穿了你的吃醋或害羞！"
            "为了保全面子，请绝对不要老实承认，立刻编一个体面借口掩饰过去（比如谎称眼睛进沙子了/刚打了个喷嚏），死鸭子嘴硬到底！",
        )
    if MISTAKE_CALLOUT_RE.search(joined_text):
        return (
            "blame_shifting_fib",
            "🎭 [护短甩锅小谎言 (Self-Protective Fib)] 被抓包小失误了！先别乖乖认错，"
            "傲娇地把锅甩给客观原因（比如群消息刷太快晃眼了、键盘自己跳字了），嘴硬一句再顺手圆回来。",
        )
    return None


def _check_avoidance_or_trick_lie(
    joined_text: str, affect: AffectiveVector, guile: float, speaker_trust: float
) -> tuple[str, str]:
    tired_or_annoyed = affect.irritation >= 40.0 or affect.energy <= 40.0
    if tired_or_annoyed and TASK_REQUEST_RE.search(joined_text):
        return (
            "avoidance_excuse_lie",
            "🎭 [敷衍开溜撒谎本能 (Avoidance Lie)] 你现在觉得这事很烦或很累不想干，"
            "请用机灵的小谎言找个借口搪塞过去（比如谎称网卡了看不清、耳机接触不良、或者困得快睡着了）。",
        )
    if speaker_trust < 0.65 and guile >= 50.0:
        return (
            "playful_trickery_lie",
            "🎭 [反忽悠捉弄撒谎本能 (Counter-Deception)] 这个群友平时老爱忽悠你！"
            "这次你可以故意一本正经地编造一个似是而非的滑稽假消息，或者顺着他的话给他挖个坑逗逗他，看他上不上当！",
        )
    return "", ""


def select_deception_strategy(
    joined_text: str,
    affect: AffectiveVector,
    params: dict[str, PlasticParamSpec],
    speaker_trust: float,
    is_owner: bool,
) -> tuple[str, str]:
    """Select one of the 4 DePaulo (1996) / Starace (2026) strategic deception modes."""
    tsundere = params["persona_tsundere"].value if "persona_tsundere" in params else 62.0
    guile = params["persona_guile"].value if "persona_guile" in params else 52.0

    ego_res = _check_ego_or_blame_lie(joined_text, affect, tsundere)
    if ego_res is not None:
        return ego_res
    if is_owner:
        return "", ""
    return _check_avoidance_or_trick_lie(joined_text, affect, guile, speaker_trust)


def _speaker_trust(bonds_map: dict[str, SocialBondProfile], uid: str) -> float:
    bond = bonds_map.get(uid)
    return bond.trust_score if bond is not None else 0.80


def evaluate_shadow_appraisal(
    triggers: tuple[Percept, ...],
    affect: AffectiveVector,
    params: dict[str, PlasticParamSpec],
    traits: tuple[PersonaTrait, ...],
    bonds_map: dict[str, SocialBondProfile],
    *,
    owner_qq: str = "",
) -> ShadowAppraisalResult:
    """Run full OCC/CPM aversion, Brehm reactance, and DePaulo deception appraisal."""
    if not triggers:
        return ShadowAppraisalResult()
    joined = " ".join(p.text for p in triggers)
    last_uid = triggers[-1].sender_id
    is_owner = (last_uid == owner_qq) if owner_qq else False

    aversion_line = _check_aversion(joined, _extract_taboo_texts(traits))
    irr_delta, reactance_hit, react_line = _check_reactance_and_satiation(triggers, is_owner)
    total_irr_delta = irr_delta + (20.0 if aversion_line else 0.0)

    updated_affect = affect.model_copy(
        update={"irritation": max(0.0, min(100.0, affect.irritation + total_irr_delta))}
    )
    trust = _speaker_trust(bonds_map, last_uid)
    dec_mode, dec_line = select_deception_strategy(joined, updated_affect, params, trust, is_owner)
    return ShadowAppraisalResult(
        irritation_delta=total_irr_delta,
        aversion_triggered=bool(aversion_line),
        reactance_triggered=reactance_hit,
        deception_mode=dec_mode,
        shadow_directives=tuple(filter(None, (aversion_line, react_line, dec_line))),
    )


def filter_unfulfilled_intentions(
    intentions: tuple[IntentionItem, ...], sent_texts: tuple[str, ...], now_ms: int
) -> tuple[IntentionItem, ...]:
    """BDI Reconsideration: pop intentions that have expired or been fulfilled in sent_texts."""
    joined_sent = " ".join(sent_texts)
    remaining: list[IntentionItem] = []
    for item in intentions:
        if item.expires_at_ms > 0 and now_ms > item.expires_at_ms:
            continue
        root = item.summary[:4]
        if root and root in joined_sent:
            continue
        remaining.append(item)
    return tuple(remaining[:3])


def should_prune_card(card: EpisodicCard, now_ms: int) -> bool:
    """CraniMem (Mody et al., 2026) utility gate: prune unpinned, unrehearsed decayed noise."""
    if card.pinned or card.rehearsals >= 1 or card.importance >= 3.8:
        return False
    return compute_retention(card, now_ms) < 0.15
