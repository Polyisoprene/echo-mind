"""M4.2 Anti-Matthew Sticker Rotation & CognitiveFrame Prompt Composer."""

from __future__ import annotations

import datetime
import hashlib
from typing import Any

from echomind.domain.models import AffectiveVector, CognitiveFrame, FrozenValueObject, Percept
from echomind.mind.naming import bot_naming

CST = datetime.timezone(datetime.timedelta(hours=8))
GAP_BREAK_MS = 300_000

def must_reply_hint(must_reply: bool) -> str:
    """Return the direct-address or group-etiquette reminder for this turn."""
    if must_reply:
        return (
            "⚡【最高优先级提醒】本轮有人直接点名/引用/私聊找你，哪怕其他机器人(如汐)已先回，"
            "你也必须调用 send_message / feiyu_say / feiyu_cover 亲自回应！"
        )
    return (
        "💡【群聊分寸提醒】本轮无人显式点名/@你！若《已读上下文》显示两位群友正在"
        "互相讨论游戏/事务（而非对你说话），请直接保持安静结束本轮（不调用任何发送工具）；"
        "仅在话题真正适合你自然搭话时调用 send_message 或 feiyu_say。"
    )


SCENE_TAGS = (
    "开心",
    "卖萌",
    "无语",
    "委屈",
    "嫌弃",
    "惊讶",
    "害羞",
    "生气",
    "发呆",
)


class StickerCandidate(FrozenValueObject):
    """Immutable sticker candidate for prompt pool rotation."""

    sticker_id: str
    description: str
    use_count: int = 0
    tags: tuple[str, ...] = ()


def preferred_tags(affect: AffectiveVector) -> frozenset[str]:
    """Map the current affective vector to the sticker tags that fit this mood."""
    wanted: set[str] = set()
    if affect.irritation >= 25.0:
        wanted.update({"嫌弃", "无语", "生气"})
    if affect.jealousy >= 18.0:
        wanted.update({"委屈", "生气"})
    if affect.shyness >= 28.0:
        wanted.update({"害羞"})
    if affect.energy <= 35.0:
        wanted.update({"发呆"})
    if affect.valence >= 55.0 and affect.irritation < 25.0 and affect.jealousy < 25.0:
        wanted.update({"开心", "卖萌"})
    return frozenset(wanted)


def _rotation_jitter(sticker_id: str, bucket: int) -> int:
    digest = hashlib.md5(f"{sticker_id}:{bucket}".encode(), usedforsecurity=False).digest()
    return digest[0] % 15


def select_rotated_stickers(
    pool: tuple[StickerCandidate, ...],
    now_ms: int,
    limit: int = 24,
    mood_tags: frozenset[str] = frozenset(),
) -> tuple[StickerCandidate, ...]:
    """Rank stickers by mood fit, inverse popularity and a 15-minute rotation jitter."""
    described = [s for s in pool if s.description.strip()]
    if not described:
        return ()
    bucket = now_ms // 900_000
    scored = [(_sticker_score(s, bucket, mood_tags), s) for s in described]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return tuple(item for _, item in scored[:limit])


def _sticker_score(sticker: StickerCandidate, bucket: int, mood_tags: frozenset[str]) -> int:
    """Higher is better: mood match first, then rarity, then rotation jitter."""
    mood_bonus = 60 if mood_tags & set(sticker.tags) else 0
    return mood_bonus - (sticker.use_count * 4) + _rotation_jitter(sticker.sticker_id, bucket)


def _fmt_time_tag(ts_ms: int) -> str:
    if ts_ms <= 100_000_000_000:
        return ""
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=CST)
    return f"[{dt.strftime('%H:%M')}] "


def _format_percept_line(p: Percept) -> str:
    quote_prefix = f"[引用 {p.quoted_text}] " if p.quoted_text else ""
    at_prefix = "[@你] " if (p.is_at_me or p.is_called_by_name) else ""
    head = f"{_fmt_time_tag(p.timestamp_ms)}[#{p.message_id}] {p.sender_name}(QQ:{p.sender_id})"
    return f"{head}: {quote_prefix}{at_prefix}{p.text}"


def _build_gap_notice(prev_ts: int, unread_triggers: tuple[Percept, ...]) -> str:
    if not unread_triggers or prev_ts <= 0:
        return ""
    diff_ms = unread_triggers[0].timestamp_ms - prev_ts
    if diff_ms < GAP_BREAK_MS:
        return ""
    mins = round(diff_ms / 60_000)
    return (
        f"⏱️【时间流逝断层提醒】距离上一条历史消息已过去 {mins} 分钟！"
        "你之前发过的话或视频早已翻篇，对方现在开启的是新话题，"
        "请直接回应最新消息本身，切勿误以为对方还在接你之前的旧话！"
    )


def _render_temporal_history(
    read_history: tuple[Percept, ...], unread_triggers: tuple[Percept, ...]
) -> tuple[list[str], str]:
    if not read_history:
        return ["（暂无早期历史）"], ""
    lines: list[str] = []
    prev_ts = 0
    for p in read_history:
        if prev_ts > 0 and (p.timestamp_ms - prev_ts) >= GAP_BREAK_MS:
            mins = round((p.timestamp_ms - prev_ts) / 60_000)
            lines.append(f"── ⏱️ [时间断层：中间安静了 {mins} 分钟，旧话题已翻篇] ──")
        lines.append(_format_percept_line(p))
        if p.timestamp_ms > 0:
            prev_ts = p.timestamp_ms
    return lines, _build_gap_notice(prev_ts, unread_triggers)


def _build_sticker_block(
    stickers: tuple[StickerCandidate, ...], now_ms: int, mood_tags: frozenset[str] = frozenset()
) -> str:
    rotated = select_rotated_stickers(stickers, now_ms, limit=24, mood_tags=mood_tags)
    if not rotated:
        return ""
    lines = [f"- {s.sticker_id}: {s.description}" for s in rotated]
    return "【可用表情包（调用 send_sticker 传入冒号前的 sticker_id）】\n" + "\n".join(lines)


EPISTEMIC_HIERARCHY_NOTE = (
    "【⚖️ 人设与记忆冲突消解最高准则（Epistemic Hierarchy）】\n"
    "1. 基础人设最高权威：你的物种、外貌与核心身份 100% 且唯一由上方基础人设决定。\n"
    "2. 冲突旧记忆自动降级：下方《已读上下文》《往事记忆》《专属默契》与《生长出的习惯》"
    "若出现与当前基础人设冲突的说法（如以前开玩笑自称过不符当前人设的身体部位或套用了"
    "其他群友的设定），一律视为早已作废的旧玩笑！当被指出冲突时必须顺从当前基础人设，"
    "严禁拿旧记忆反驳基础人设。\n"
    "3. 防复读与话题饱和：若《已读上下文》最近几句里已提过某个具体物品、食物或手头动作，"
    "除非对方本轮直接追问，否则禁止再次主动提起同一个词，自然切换新话题。"
)


VOICE_AND_SPEAK_GUIDE = (
    "【🗣️ 说话、发语音与唱歌表达指南】\n"
    "1. 文字回复（send_message）：把想说的话合并成 1 条消息发出，不要手写 @昵称。\n"
    "2. 真语音开口说话（feiyu_say）：你有自己好听的嗓子（GPU 常驻，约 10 秒合成），"
    "想发语音就主动发，不用等别人要求！当撒娇、哄人、道晚安、吃醋哼哼、情绪化短句、"
    "或跟在意的人私聊想让他听见你语气时，直接调用 feiyu_say 代替 send_message"
    "（发了语音就别再把同一句话发文字）。\n"
    "3. 带伴奏唱完整首歌（feiyu_cover）：当任何人让你唱首歌、点歌"
    "（如『唱首晴天』『来首歌』）或发来 B站音乐让你翻唱时，直接调 feiyu_cover 传入歌名或BV号！\n"
    "4. 分享B站视频必带链接铁律：当你主动向对方推荐/分享你在B站刷到的视频（如说『你看这个视频』），"
    "或对方问你『视频呢/链接呢/发来看看』时，必须调用 send_message 把『正在做的事/权威事实』里"
    "的完整视频链接 https://www.bilibili.com/video/BV...（若不知链接可先调 bili_search 查出链接）"
    "直接发给对方，切勿只说空话不发链接，也不要调 watch_video 去找对方没发的视频！\n"
    "5. 多步深度思考与主动查证（ReAct）：当对话涉及回忆往事、认人、未知热梗、转发记录或图片时，"
    "不要急着第1步就调 send_message！请先调用 recall_memory（深度翻找记忆库）/ get_group_members / "
    "web_search / read_forward / look_at_image 收集足够信息，想透彻后再开口回应。"
)


class PromptComposer:
    """Pure assembler rendering Role + Rotated Stickers + CognitiveFrame + Messages."""

    def __init__(
        self, role_text: str, bot_name: str = "", *, persona_in_system: bool = False
    ) -> None:
        self._role_text = role_text
        self._bot_name = bot_name or bot_naming().label()
        self._persona_in_system = persona_in_system

    def role_card(self) -> tuple[str, str]:
        return self._bot_name, self._role_text

    def update_role_card(self, bot_name: str, role_text: str) -> None:
        if bot_name.strip():
            self._bot_name = bot_name.strip()
        self._role_text = role_text.strip()

    def compose(
        self,
        frame: CognitiveFrame,
        read_history: tuple[Percept, ...],
        unread_triggers: tuple[Percept, ...],
        stickers: tuple[StickerCandidate, ...] = (),
        now_ms: int = 0,
    ) -> list[dict[str, Any]]:
        sticker_block = _build_sticker_block(stickers, now_ms, preferred_tags(frame.affect))
        must_hint = must_reply_hint(frame.must_reply)
        sys_parts = [
            f"你是「{self._bot_name}」。{self._role_text}",
            EPISTEMIC_HIERARCHY_NOTE,
            sticker_block,
            VOICE_AND_SPEAK_GUIDE,
        ]
        if self._persona_in_system:
            sys_parts.append(frame.rendered_mind_block)
        read_lines, gap_note = _render_temporal_history(read_history, unread_triggers)
        unread_lines = [_format_percept_line(p) for p in unread_triggers]
        user_blocks = [
            "【已读上下文（带北京时间，注意 ⏱️ 时间断层）】\n" + "\n".join(read_lines),
            "" if self._persona_in_system else frame.rendered_mind_block,
            gap_note,
            must_hint,
            "【最新待处理消息】\n" + "\n".join(unread_lines),
        ]
        user_content = "\n\n".join(b for b in user_blocks if b)
        return [
            {"role": "system", "content": "\n\n".join(p for p in sys_parts if p)},
            {"role": "user", "content": user_content},
        ]
