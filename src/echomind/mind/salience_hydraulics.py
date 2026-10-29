"""M21.1 Ecological Salience Scorer, Dyadic DND, Self-Utterance Resonance & Lorenz Hydraulics."""

from __future__ import annotations

import re

from echomind.domain.models import (
    AttentionDecision,
    DriveState,
    Percept,
    PlasticParamSpec,
    WorkingSnapshot,
)
from echomind.mind.ebbinghaus import tokenize_query

AT_UID_RE = re.compile(r"\(QQ:(\d{3,12})\)|@(\d{3,12})")
TRIVIAL_NOISE_RE = re.compile(
    r"^(?:[哈嘿呵啊哦嗯草6？?！!\.。，,~～]+|确实|好家伙|牛的|笑死|真的假的|\[表情\]|\[图片\])$"
)
OPEN_QUESTION_RE = re.compile(r"[？?]|大家觉得|有人知道|为什么|啥意思|怎么回事")
RESONANCE_CUE_RE = re.compile(r"真的吗|什么视频|哪个视频|发来看看|链接呢|叫啥名字|好听吗")
SKILL_REQUEST_RE = re.compile(r"唱首歌|唱一首|来首歌|发个语音|说句语音")
SECOND_PERSON_ASK_RE = re.compile(r"你在干嘛|你睡了吗|你觉得呢|你知道.{1,10}吗|你会.{1,8}吗")


def extract_at_target_uid(text: str) -> str:
    """Extract the target QQ ID from an @mention segment in percept text."""
    m = AT_UID_RE.search(text)
    if not m:
        return ""
    return str(m.group(1) or m.group(2) or "")


def record_dyadic_pair(
    dyad_map: dict[str, tuple[str, str, int]],
    percept: Percept,
    target_uid: str,
    fallback_peer_uid: str = "",
) -> None:
    """Open a 90-second Dyadic Do-Not-Disturb window between sender and @target/peer."""
    peer = target_uid or fallback_peer_uid
    if percept.sender_id and peer and percept.sender_id != peer:
        dyad_map[percept.chat_key] = (
            percept.sender_id,
            peer,
            percept.timestamp_ms + 90_000,
        )


def is_in_dyadic_dnd(
    dyad_map: dict[str, tuple[str, str, int]], percept: Percept, owner_qq: str = ""
) -> bool:
    """Return True if two non-owner peers are in an active 60s 1-on-1 exchange."""
    entry = dyad_map.get(percept.chat_key)
    if not entry:
        return False
    uid_a, uid_b, until_ms = entry
    if percept.timestamp_ms > until_ms:
        return False
    if owner_qq and percept.sender_id == owner_qq:
        return False
    return percept.sender_id in (uid_a, uid_b)


def _is_rival_sender(percept: Percept, rivals: tuple[str, ...]) -> bool:
    return any(r in percept.sender_name or r == percept.sender_id for r in rivals if r)


def check_self_utterance_resonance(
    percept: Percept,
    bot_speech: dict[str, tuple[int, str, int]],
    rivals: tuple[str, ...],
    *,
    record_state: bool = True,
) -> tuple[bool, str]:
    """Check if a group message is replying to Echo's recent words (with 2-round cap)."""
    entry = bot_speech.get(percept.chat_key)
    if not entry:
        return False, ""
    spoke_ts, spoke_text, chain_depth = entry
    dt_ms = percept.timestamp_ms - spoke_ts
    max_depth = 1 if _is_rival_sender(percept, rivals) else 2
    if not (0 <= dt_ms <= 120_000) or chain_depth >= max_depth:
        return False, ""
    overlap = tokenize_query(percept.text) & tokenize_query(spoke_text)
    cue_hit = dt_ms <= 60_000 and bool(RESONANCE_CUE_RE.search(percept.text))
    if not overlap and not cue_hit:
        return False, ""
    if record_state:
        bot_speech[percept.chat_key] = (spoke_ts, spoke_text, chain_depth + 1)
    return True, f"接我的话茬·余音共鸣(第{chain_depth + 1}轮)"


def check_implicit_second_person_ask(
    percept: Percept, last_group_ts: int, last_bot_ts: int
) -> str:
    """Disambiguate un-@'d second-person questions or bot skill requests."""
    if SKILL_REQUEST_RE.search(percept.text):
        return "群友点歌/语音互动请求"
    if not SECOND_PERSON_ASK_RE.search(percept.text):
        return ""
    bot_recent = last_bot_ts > 0 and (percept.timestamp_ms - last_bot_ts) <= 90_000
    group_was_idle = last_group_ts <= 0 or (percept.timestamp_ms - last_group_ts) >= 180_000
    if bot_recent or group_was_idle:
        return "向我发问(第二人称消解通过)"
    return ""


def _p_val(params: dict[str, PlasticParamSpec] | None, key: str, default: float) -> float:
    if not params or key not in params:
        return default
    return params[key].value


def _positive_factors(
    percept: Percept,
    working: WorkingSnapshot,
    unknowns: tuple[str, ...],
    has_unseen: bool,
    *,
    known_vocab: frozenset[str],
    owner_qq: str,
    params: dict[str, PlasticParamSpec] | None,
) -> tuple[float, list[str]]:
    bonus = 0.0
    tags: list[str] = []
    if owner_qq and percept.sender_id == owner_qq:
        poss = _p_val(params, "persona_possessiveness", 75.0)
        b_own = round(0.14 + 0.14 * (poss / 100.0), 2)
        bonus += b_own
        tags.append(f"+主人{b_own}")
    if OPEN_QUESTION_RE.search(percept.text):
        warm = _p_val(params, "persona_warmth", 65.0)
        b_q = round(0.06 + 0.06 * (warm / 100.0), 2)
        bonus += b_q
        tags.append(f"+提问{b_q}")
    if unknowns:
        play = _p_val(params, "persona_playfulness", 70.0)
        cur_scale = 0.5 + 0.5 * (working.drives.curiosity / 100.0)
        b_unk = round((0.14 + 0.12 * (play / 100.0)) * cur_scale, 2)
        bonus += b_unk
        tags.append(f"+新词{b_unk}")
    elif has_unseen and working.drives.curiosity >= 42.0:
        b_img = round(0.08 * (working.drives.curiosity / 100.0), 2)
        bonus += b_img
        tags.append(f"+媒体{b_img}")
    act_tokens = tokenize_query(working.current_activity)
    msg_tokens = tokenize_query(percept.text)
    if (act_tokens & msg_tokens) or any(t in known_vocab for t in msg_tokens):
        conf = _p_val(params, "persona_confidence", 65.0)
        b_top = round(0.09 + 0.07 * (conf / 100.0), 2)
        bonus += b_top
        tags.append(f"+共鸣{b_top}")
    return bonus, tags


def _negative_factors(
    percept: Percept,
    working: WorkingSnapshot,
    unknowns: tuple[str, ...],
    has_unseen: bool,
    params: dict[str, PlasticParamSpec] | None,
) -> tuple[float, list[str]]:
    penalty = 0.0
    tags: list[str] = []
    txt = percept.text.strip()
    if (len(txt) < 4 and not unknowns and not has_unseen) or TRIVIAL_NOISE_RE.match(txt):
        penalty += 0.18
        tags.append("-水群0.18")
    if working.affect.irritation >= 20.0:
        defi = _p_val(params, "persona_defiance", 60.0)
        p_irr = round((working.affect.irritation / 100.0) * (0.14 + 0.10 * (defi / 100.0)), 2)
        penalty += p_irr
        tags.append(f"-厌烦{p_irr}")
    if working.affect.energy < 55.0:
        p_fat = round((55.0 - working.affect.energy) / 200.0, 2)
        penalty += p_fat
        tags.append(f"-困倦{p_fat}")
    drv_bias = round((working.drives.social_expression - 42.0) / 300.0, 2)
    if drv_bias < -0.01:
        penalty += abs(drv_bias)
        tags.append(f"-刚聊完{abs(drv_bias)}")
    return penalty, tags


def evaluate_bidirectional_ambient(
    percept: Percept, working: WorkingSnapshot, unknowns: tuple[str, ...],
    has_unseen: bool, talkativeness: float, *,
    known_vocab: frozenset[str] = frozenset(), owner_qq: str = "",
    params: dict[str, PlasticParamSpec] | None = None,
) -> AttentionDecision:
    """Compute bidirectional salience score with 7D persona conditional gain & breakdown."""
    if working.affect.energy < 22.0:
        return AttentionDecision(
            should_wake=False, salience_score=0.15, tier=0, reason="精力过低·犯困休息不插话",
            detected_unknown_terms=unknowns, has_unseen_media=has_unseen,
        )
    eff_talk = talkativeness * (0.5 + 0.5 * (working.affect.energy / 100.0))
    threshold = round(max(0.48, min(0.76, 0.86 - (eff_talk / 210.0))), 2)
    if (bool(unknowns) or has_unseen) and working.drives.curiosity >= 45.0:
        return AttentionDecision(
            should_wake=(threshold <= 0.75), salience_score=0.75, tier=3,
            reason=f"好奇心触发(未知新词或未读媒体) [0.75 vs 阈{threshold}]",
            detected_unknown_terms=unknowns, has_unseen_media=has_unseen,
        )
    pos, p_tags = _positive_factors(
        percept, working, unknowns, has_unseen,
        known_vocab=known_vocab, owner_qq=owner_qq, params=params,
    )
    neg, n_tags = _negative_factors(percept, working, unknowns, has_unseen, params)
    drv_pos = max(0.0, round((working.drives.social_expression - 42.0) / 300.0, 2))
    if drv_pos >= 0.02:
        p_tags.append(f"+表达欲{drv_pos}")
    score = round(max(0.10, min(0.84, 0.35 + pos + drv_pos - neg)), 2)
    wake = score >= threshold
    formula = " ".join(["底0.35", *p_tags, *n_tags])
    head = "群聊氛围接话" if wake else "外围静默感知"
    return AttentionDecision(
        should_wake=wake, salience_score=score, tier=3 if wake else 0,
        reason=f"{head} [{formula} = {score} {'≥' if wake else '<'} 阈{threshold}]",
        detected_unknown_terms=unknowns, has_unseen_media=has_unseen,
    )


def apply_speaking_satiation(
    snap: WorkingSnapshot, sent_texts: tuple[str, ...], tools_used: tuple[str, ...]
) -> WorkingSnapshot:
    """Lorenz hydraulic satiation discharge: drop social_expression & curiosity after speaking."""
    if not sent_texts:
        return snap
    drv, aff = snap.drives, snap.affect
    used_explore = any(t not in ("send_message", "send_sticker", "feiyu_say") for t in tools_used)
    min_cur = 46.0 if snap.curiosity_queue else 24.0
    new_soc = round(max(22.0, drv.social_expression - 22.0), 2)
    new_cur = round(max(min_cur, drv.curiosity - (20.0 if used_explore else 4.0)), 2)
    new_eng = round(max(15.0, aff.energy - 1.5), 2)
    return snap.model_copy(
        update={
            "affect": aff.model_copy(update={"energy": new_eng}),
            "drives": DriveState(
                curiosity=new_cur, attachment=drv.attachment,
                jealousy_drive=drv.jealousy_drive, social_expression=new_soc,
            ),
        }
    )
