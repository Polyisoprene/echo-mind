"""M3.1 Perceptual, Salience & Cold-Shoulder Gate (Thalamus Router & Knowledge Gap Detector)."""

from __future__ import annotations

import re
from typing import Literal

from echomind.domain.models import (
    AttentionDecision,
    Percept,
    PlasticParamSpec,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.mind.salience_hydraulics import (
    check_implicit_second_person_ask,
    check_self_utterance_resonance,
    evaluate_bidirectional_ambient,
    extract_at_target_uid,
    is_in_dyadic_dnd,
    record_dyadic_pair,
)

QUOTED_TERM_RE = re.compile(r"[「『《“\"【]([\u4e00-\u9fa5A-Za-z0-9]{2,10})[」』》”\"】]")
ASK_MEME_RE = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9]{2,8})(?:是什么梗|是什么意思|是什么|是谁呀|怎么看|厉害了|太强了)"
)
URL_BV_STRIP_RE = re.compile(r"https?://\S+|b23\.tv/\S+|BV[0-9A-Za-z]{10}|www\.\S+")
ALNUM_TERM_RE = re.compile(r"\b[A-Za-z]{2,12}\b")
EN_STOPWORDS = frozenset(
    {
        "the", "and", "for", "you", "are", "was", "but", "not", "with", "this", "that",
        "img", "image", "jpg", "png", "gif", "cq", "file", "url", "http", "https",
        "appid", "qq", "ai", "ok", "hi", "id", "bv", "up", "api", "llm", "dsh", "bug",
        "ui", "json", "www", "com", "cn", "net", "org", "tv", "bilibili", "xiaohongshu",
        "workbuddy", "codebuddy", "token", "git", "github",
    }
)
COMMON_STOPWORDS = frozenset(
    {"回音", "尾尾", "什么", "怎么", "这个", "那个", "哈哈", "图片", "表情"}
)


def extract_unknown_terms(text: str, known_vocab: frozenset[str]) -> tuple[str, ...]:
    """Extract genuine domain terms/memes (quoted, asked-about, or proper nouns)."""
    stripped = URL_BV_STRIP_RE.sub(" ", text)
    candidates = [
        *QUOTED_TERM_RE.findall(stripped),
        *ASK_MEME_RE.findall(stripped),
        *ALNUM_TERM_RE.findall(stripped),
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


def _is_rival_speaker(percept: Percept, rivals: tuple[str, ...]) -> bool:
    return any(r and (r in percept.sender_name or r == percept.sender_id) for r in rivals)


def _match_intention_slice(text: str, working: WorkingSnapshot) -> str:
    for item in working.intentions:
        key_slice = item.summary[:4]
        if key_slice and key_slice in text:
            return f"命中短期挂念({key_slice})"
    return ""


def _hits_working_focus(
    percept: Percept, working: WorkingSnapshot, rivals: tuple[str, ...], owner_qq: str = ""
) -> str:
    intent_hit = _match_intention_slice(percept.text, working)
    if intent_hit or _is_rival_speaker(percept, rivals):
        return intent_hit
    hit_r = next((r for r in rivals if r and r in percept.text), "")
    return f"提及吃醋关注对象({hit_r})" if hit_r else ""


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
        self._dyadic_dnd: dict[str, tuple[str, str, int]] = {}
        self._bot_speech: dict[str, tuple[int, str, int]] = {}
        self._last_group_ts: dict[str, int] = {}
        self._last_peer: dict[str, tuple[str, int]] = {}

    def mark_replied_to(self, chat_key: str, user_id: str, now_ms: int) -> None:
        """Open or renew a short-followup window for a user we just answered."""
        self._followup_until[f"{chat_key}::{user_id}"] = now_ms + self._followup_ttl_ms

    def mark_bot_spoke(
        self, chat_key: str, texts: tuple[str, ...], now_ms: int, triggers: tuple[Percept, ...] = ()
    ) -> None:
        """Record Echo's latest spoken text and open followup only for explicit summoners."""
        joined = " ".join(t.strip() for t in texts if t.strip())
        if joined:
            prev = self._bot_speech.get(chat_key)
            depth = prev[2] if (prev and (now_ms - prev[0]) <= 120_000) else 0
            self._bot_speech[chat_key] = (now_ms, joined[:180], depth)
        for p in triggers:
            if _is_direct_summon(p)[0]:
                self.mark_replied_to(chat_key, p.sender_id, now_ms)

    def impose_cold_shoulder(
        self, chat_key: str, user_id: str, now_ms: int, duration_ms: int = 900_000
    ) -> None:
        """Block an annoying non-owner user for 15 minutes (Silent Treatment)."""
        self._cold_shoulder_until[f"{chat_key}::{user_id}"] = now_ms + duration_ms

    def mark_ambient_wake(self, chat_key: str, now_ms: int) -> None:
        """Arm the post-ambient-wake cooldown window for a chat."""
        self._last_ambient_wake_ms[chat_key] = now_ms

    def ambient_cooldown_active(self, chat_key: str, now_ms: int) -> bool:
        """Return True while the chat sits inside the post-ambient-wake cooldown window."""
        last = self._last_ambient_wake_ms.get(chat_key, 0)
        return last > 0 and (now_ms - last) < self._ambient_cooldown_ms

    def _in_cold_shoulder(self, percept: Percept) -> bool:
        key = f"{percept.chat_key}::{percept.sender_id}"
        return percept.timestamp_ms <= self._cold_shoulder_until.get(key, 0)

    def _peer_interleaved(self, percept: Percept) -> bool:
        prev = self._last_peer.get(percept.chat_key)
        if not prev or prev[0] == percept.sender_id:
            return False
        return (percept.timestamp_ms - prev[1]) <= 45_000

    def _in_followup(
        self, percept: Percept, rivals: tuple[str, ...] = (), *, record_state: bool = True
    ) -> bool:
        key = f"{percept.chat_key}::{percept.sender_id}"
        if _is_rival_speaker(percept, rivals) or percept.timestamp_ms > self._followup_until.get(
            key, 0
        ):
            return False
        if record_state:
            self._followup_until.pop(key, None)
        return not self._peer_interleaved(percept)

    def _check_direct_or_other_at(
        self, percept: Percept, unknowns: tuple[str, ...], has_unseen: bool, *, record_state: bool
    ) -> AttentionDecision | None:
        is_direct, direct_reason = _is_direct_summon(percept)
        if is_direct:
            if record_state and percept.chat_key in self._bot_speech:
                ts, txt, _ = self._bot_speech[percept.chat_key]
                self._bot_speech[percept.chat_key] = (ts, txt, 0)
            return _wake_dec(1.0, 1, direct_reason, unknowns, has_unseen)
        if bool(extract_at_target_uid(percept.text)) or (
            percept.quoted_message_id and not percept.is_quoted_me
        ):
            if record_state:
                self._followup_until.pop(f"{percept.chat_key}::{percept.sender_id}", None)
                prev_u = self._last_peer.get(percept.chat_key, ("", 0))[0]
                record_dyadic_pair(
                    self._dyadic_dnd, percept, extract_at_target_uid(percept.text), prev_u
                )
            return _wake_dec(0.05, 0, "艾特其他群友(非对我说话)", unknowns, has_unseen, wake=False)
        return None

    def _check_tier2_continuation(
        self,
        percept: Percept,
        working: WorkingSnapshot,
        rivals: tuple[str, ...],
        unknowns: tuple[str, ...],
        has_unseen: bool,
        *,
        record_state: bool,
        owner_qq: str = "",
    ) -> AttentionDecision | None:
        if is_in_dyadic_dnd(self._dyadic_dnd, percept, owner_qq=owner_qq):
            return _wake_dec(
                0.12, 0, "群友二人互动中·礼貌不打扰 [0.12]", unknowns, has_unseen, wake=False
            )
        focus_hit = _hits_working_focus(percept, working, rivals, owner_qq)
        if focus_hit or self._in_followup(percept, rivals, record_state=record_state):
            return _wake_dec(0.85, 2, focus_hit or "短期跟聊窗口内", unknowns, has_unseen)
        res_hit, res_reason = check_self_utterance_resonance(
            percept, self._bot_speech, rivals, record_state=record_state
        )
        if res_hit:
            return _wake_dec(0.86, 2, res_reason, unknowns, has_unseen)
        last_g_ts = self._last_group_ts.get(percept.chat_key, 0)
        bot_entry = self._bot_speech.get(percept.chat_key)
        last_b_ts = bot_entry[0] if bot_entry else 0
        ask_reason = check_implicit_second_person_ask(percept, last_g_ts, last_b_ts)
        if ask_reason:
            return _wake_dec(0.84, 2, ask_reason, unknowns, has_unseen)
        return None

    def _evaluate_ambient_with_cooldown(
        self, percept: Percept, working: WorkingSnapshot, unknowns: tuple[str, ...],
        has_unseen: bool, talkativeness: float, *, record_state: bool,
        known_vocab: frozenset[str] = frozenset(), owner_qq: str = "",
        params: dict[str, PlasticParamSpec] | None = None,
        speaker_bond: SocialBondProfile | None = None,
    ) -> AttentionDecision:
        if is_in_dyadic_dnd(self._dyadic_dnd, percept, owner_qq=owner_qq):
            return _wake_dec(
                0.12, 0, "群友二人互动中·礼貌不打扰 [0.12]", unknowns, has_unseen, wake=False
            )
        if record_state and self.ambient_cooldown_active(
            percept.chat_key, percept.timestamp_ms
        ):
            return _wake_dec(0.30, 0, "群聊非点名冷却期内", unknowns, has_unseen, wake=False)
        dec = evaluate_bidirectional_ambient(
            percept, working, unknowns, has_unseen, talkativeness,
            known_vocab=known_vocab, owner_qq=owner_qq, params=params, speaker_bond=speaker_bond,
        )
        if dec.should_wake and record_state:
            self._last_ambient_wake_ms[percept.chat_key] = percept.timestamp_ms
        return dec

    def evaluate(
        self, percept: Percept, working: WorkingSnapshot,
        known_vocab: frozenset[str] = frozenset(), rivals: tuple[str, ...] = (),
        talkativeness: float = 58.0, *, record_state: bool = True, owner_qq: str = "",
        params: dict[str, PlasticParamSpec] | None = None,
        speaker_bond: SocialBondProfile | None = None,
    ) -> AttentionDecision:
        """Compute salience score, cold-shoulder block, and wake decision."""
        if self._in_cold_shoulder(percept):
            return _wake_dec(0.0, 0, "重度厌烦·15分钟冷暴力已读不回", (), False, wake=False)
        has_unseen = any(not m.description for m in percept.media)
        unknowns = extract_unknown_terms(percept.text, known_vocab)
        direct_dec = self._check_direct_or_other_at(
            percept, unknowns, has_unseen, record_state=record_state
        )
        if direct_dec is not None:
            if record_state:
                self._last_group_ts[percept.chat_key] = percept.timestamp_ms
                self._last_peer[percept.chat_key] = (percept.sender_id, percept.timestamp_ms)
            return direct_dec
        t2_dec = self._check_tier2_continuation(
            percept, working, rivals, unknowns, has_unseen,
            record_state=record_state, owner_qq=owner_qq,
        )
        if record_state:
            self._last_group_ts[percept.chat_key] = percept.timestamp_ms
            self._last_peer[percept.chat_key] = (percept.sender_id, percept.timestamp_ms)
        if t2_dec is not None:
            return t2_dec
        return self._evaluate_ambient_with_cooldown(
            percept, working, unknowns, has_unseen, talkativeness,
            record_state=record_state, known_vocab=known_vocab,
            owner_qq=owner_qq, params=params, speaker_bond=speaker_bond,
        )
