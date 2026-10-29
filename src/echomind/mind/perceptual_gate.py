"""M3.1 Perceptual, Salience & Cold-Shoulder Gate (Thalamus Router & Knowledge Gap Detector)."""

from __future__ import annotations

import re
from typing import Literal

from echomind.domain.models import AttentionDecision, Percept, WorkingSnapshot

# Genuine unknown terms: quoted terms, "XX是什么梗", or alphanumeric proper nouns
QUOTED_TERM_RE = re.compile(r"[「『《“\"【]([\u4e00-\u9fa5A-Za-z0-9]{2,10})[」』》”\"】]")
ASK_MEME_RE = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9]{2,8})(?:是什么梗|是什么意思|是什么|是谁呀|怎么看|厉害了|太强了)"
)
# 只把纯字母单词当作可疑专有名词；带连字符/数字的多半是文件名、UUID 或 MD5 片段
ALNUM_TERM_RE = re.compile(r"\b[A-Za-z]{2,12}\b")
EN_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "you",
        "are",
        "was",
        "but",
        "not",
        "with",
        "this",
        "that",
        "img",
        "image",
        "jpg",
        "png",
        "gif",
        "cq",
        "file",
        "url",
        "http",
        "https",
        "appid",
        "qq",
        "ai",
        "ok",
        "hi",
        "id",
        "bv",
        "up",
        "api",
        "llm",
        "dsh",
        "bug",
        "ui",
        "json",
    }
)
COMMON_STOPWORDS = frozenset(
    {"回音", "尾尾", "什么", "怎么", "这个", "那个", "哈哈", "图片", "表情"}
)


def extract_unknown_terms(text: str, known_vocab: frozenset[str]) -> tuple[str, ...]:
    """Extract genuine domain terms/memes (quoted, asked-about, or proper nouns)."""
    candidates = [
        *QUOTED_TERM_RE.findall(text),
        *ASK_MEME_RE.findall(text),
        *ALNUM_TERM_RE.findall(text),
    ]
    unknown = [
        term
        for term in (c.strip() for c in candidates)
        if len(term) >= 2
        and term not in COMMON_STOPWORDS
        and term.lower() not in EN_STOPWORDS
        and term.lower() not in known_vocab
    ]
    return tuple(dict.fromkeys(unknown))[:3]


def _is_direct_summon(percept: Percept) -> tuple[bool, str]:
    if percept.scene == "private":
        return True, "私聊直接对话"
    if percept.is_at_me:
        return True, "被艾特(@我)"
    if percept.is_called_by_name:
        return True, "点名叫我(必回)"
    if percept.is_quoted_me:
        return True, "引用回复我"
    if percept.is_poke_me:
        return True, "拍了拍我"
    return False, ""


def _hits_working_focus(text: str, working: WorkingSnapshot, rivals: tuple[str, ...]) -> str:
    for item in working.intentions:
        key_slice = item.summary[:4]
        if key_slice and key_slice in text:
            return f"命中短期挂念({key_slice})"
    for rival in rivals:
        if rival and rival in text:
            return f"提及吃醋关注对象({rival})"
    return ""


def _evaluate_ambient_or_curiosity(
    percept: Percept,
    working: WorkingSnapshot,
    unknowns: tuple[str, ...],
    has_unseen: bool,
    talkativeness: float,
) -> AttentionDecision:
    if working.affect.energy < 22.0:
        return _wake_dec(0.15, 0, "精力过低·犯困休息不插话", unknowns, has_unseen, wake=False)
    eff_talk = talkativeness * (0.5 + 0.5 * (working.affect.energy / 100.0))
    wake_threshold = max(0.45, min(0.82, 0.90 - (eff_talk / 200.0)))
    has_gap = bool(unknowns) or has_unseen
    if has_gap and working.drives.curiosity >= 45.0:
        return AttentionDecision(
            should_wake=(wake_threshold <= 0.75),
            salience_score=0.75,
            tier=3,
            reason="好奇心触发(未知新词或未读媒体)",
            detected_unknown_terms=unknowns,
            has_unseen_media=has_unseen,
        )
    base_salience = 0.55 if len(percept.text.strip()) >= 4 else 0.20
    should_wake = base_salience >= wake_threshold
    return AttentionDecision(
        should_wake=should_wake,
        salience_score=base_salience,
        tier=3 if should_wake else 0,
        reason="群聊氛围接话" if should_wake else "外围静默感知",
        detected_unknown_terms=unknowns,
        has_unseen_media=has_unseen,
    )


def _wake_dec(
    score: float,
    tier: Literal[0, 1, 2, 3],
    reason: str,
    unknowns: tuple[str, ...],
    unseen: bool,
    *,
    wake: bool = True,
) -> AttentionDecision:
    return AttentionDecision(
        should_wake=wake,
        salience_score=score,
        tier=tier,
        reason=reason,
        detected_unknown_terms=unknowns,
        has_unseen_media=unseen,
    )


class PerceptualGate:
    """Attention router with 5-min followup window & 15-min Cold-Shoulder Silent Treatment."""

    def __init__(self, followup_ttl_ms: int = 300_000, ambient_cooldown_ms: int = 75_000) -> None:
        self._followup_ttl_ms = followup_ttl_ms
        self._ambient_cooldown_ms = ambient_cooldown_ms
        self._followup_until: dict[str, int] = {}
        self._cold_shoulder_until: dict[str, int] = {}
        self._last_ambient_wake_ms: dict[str, int] = {}

    def mark_replied_to(self, chat_key: str, user_id: str, now_ms: int) -> None:
        """Open or renew a short-followup window for a user we just answered."""
        self._followup_until[f"{chat_key}::{user_id}"] = now_ms + self._followup_ttl_ms

    def impose_cold_shoulder(
        self, chat_key: str, user_id: str, now_ms: int, duration_ms: int = 900_000
    ) -> None:
        """Block an annoying non-owner user for 15 minutes (Silent Treatment)."""
        self._cold_shoulder_until[f"{chat_key}::{user_id}"] = now_ms + duration_ms

    def _in_cold_shoulder(self, percept: Percept) -> bool:
        key = f"{percept.chat_key}::{percept.sender_id}"
        return percept.timestamp_ms <= self._cold_shoulder_until.get(key, 0)

    def _in_followup(self, percept: Percept) -> bool:
        key = f"{percept.chat_key}::{percept.sender_id}"
        return percept.timestamp_ms <= self._followup_until.get(key, 0)

    @staticmethod
    def _check_direct_or_other_at(
        percept: Percept, unknowns: tuple[str, ...], has_unseen: bool
    ) -> AttentionDecision | None:
        is_direct, direct_reason = _is_direct_summon(percept)
        if is_direct:
            return _wake_dec(1.0, 1, direct_reason, unknowns, has_unseen)
        if "@" in percept.text or (percept.quoted_message_id and not percept.is_quoted_me):
            return _wake_dec(0.05, 0, "艾特其他群友(非对我说话)", unknowns, has_unseen, wake=False)
        return None

    def _evaluate_ambient_with_cooldown(
        self,
        percept: Percept,
        working: WorkingSnapshot,
        unknowns: tuple[str, ...],
        has_unseen: bool,
        talkativeness: float,
        *,
        record_state: bool,
    ) -> AttentionDecision:
        last_amb = self._last_ambient_wake_ms.get(percept.chat_key, 0)
        if record_state and (percept.timestamp_ms - last_amb) < self._ambient_cooldown_ms:
            return _wake_dec(0.30, 0, "群聊非点名冷却期内", unknowns, has_unseen, wake=False)
        dec = _evaluate_ambient_or_curiosity(percept, working, unknowns, has_unseen, talkativeness)
        if dec.should_wake and record_state:
            self._last_ambient_wake_ms[percept.chat_key] = percept.timestamp_ms
        return dec

    def evaluate(
        self,
        percept: Percept,
        working: WorkingSnapshot,
        known_vocab: frozenset[str] = frozenset(),
        rivals: tuple[str, ...] = (),
        talkativeness: float = 58.0,
        *,
        record_state: bool = True,
    ) -> AttentionDecision:
        """Compute salience score, cold-shoulder block, and wake decision."""
        if self._in_cold_shoulder(percept):
            return _wake_dec(0.0, 0, "重度厌烦·15分钟冷暴力已读不回", (), False, wake=False)

        has_unseen = any(not m.description for m in percept.media)
        unknowns = extract_unknown_terms(percept.text, known_vocab)

        direct_dec = self._check_direct_or_other_at(percept, unknowns, has_unseen)
        if direct_dec is not None:
            return direct_dec
        focus_hit = _hits_working_focus(percept.text, working, rivals)
        if focus_hit or self._in_followup(percept):
            return _wake_dec(0.85, 2, focus_hit or "短期跟聊窗口内", unknowns, has_unseen)

        return self._evaluate_ambient_with_cooldown(
            percept, working, unknowns, has_unseen, talkativeness, record_state=record_state
        )
