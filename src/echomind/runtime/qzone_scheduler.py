"""Periodic Qzone Mood Showcase, QQ Signature & Proactive Life Messaging Scheduler."""

from __future__ import annotations

import datetime
import re

from echomind.domain.ports import (
    ILlmGateway,
    IMemoryReader,
    IMessageSender,
    IOneBotApiCaller,
    ISkillConfigStore,
    IWorkingStateStore,
)
from echomind.mind.circadian import biological_jitter_factor, resolve_circadian_phase
from echomind.mind.drives import circadian_energy_target
from echomind.mind.personality import synthesize_live_persona_directive
from echomind.runtime.qzone_budgets import budget, extract_content, is_truncated

QZONE_CFG_KEY = "qzone_showcase"
QZONE_STATE_KEY = "__qzone_state__"
CST = datetime.timezone(datetime.timedelta(hours=8))
TARGET_SPLIT_RE = re.compile(r"[,，;；\s\n]+")
PREFIX_MAP = {"group:": "group", "private:": "private", "g:": "group", "p:": "private"}


def _resolve_kind_and_num(head: str, has_at: bool) -> tuple[str, str]:
    for prefix, kind in PREFIX_MAP.items():
        if head.startswith(prefix):
            return kind, head[len(prefix) :].strip()
    if head.isdigit():
        return ("group" if has_at else "private"), head
    return "", ""


def _parse_single_target(tok: str) -> tuple[str, str | None] | None:
    raw = tok.strip()
    if not raw:
        return None
    head, at_part = raw.split("@", 1) if "@" in raw else (raw, "")
    at_uid = at_part.strip() if at_part.strip().isdigit() else None
    kind, num = _resolve_kind_and_num(head.strip(), at_uid is not None)
    if not kind or not num.isdigit():
        return None
    return f"{kind}:{num}", at_uid


def parse_proactive_targets(raw_spec: str) -> tuple[tuple[str, str | None], ...]:
    """Parse comma/space-separated multi-target specs into ((chat_key, at_uid), ...)."""
    tokens = TARGET_SPLIT_RE.split(raw_spec or "")
    valid = [p for p in (_parse_single_target(t) for t in tokens) if p is not None]
    deduped = tuple(dict.fromkeys(valid))
    return deduped[:6] if deduped else (("private:10001001", None),)


def _proactive_prompt_for(chat_key: str, at_uid: str | None) -> str:
    link_rule = (
        "（注意：如果你在话里提到或推荐了你刚在B站刷到的某个视频，必须在话里附上完整的 "
        "https://www.bilibili.com/video/BV... 链接，绝不能只说『你看这个视频』却不发链接！"
        "只输出要发的话本身，不要加引号）。"
    )
    if chat_key.startswith("group:") and at_uid:
        return (
            f"请结合当前时间和你正在做的事，在群里主动艾特群友(QQ:{at_uid})搭一句自然的话{link_rule}"
        )
    if chat_key.startswith("group:"):
        return (
            f"群里安静有一会儿了，请结合当前时间和你正在做的事，主动在群里冒个泡开个话头{link_rule}"
        )
    return f"请结合当前时间和你正在做的事，主动给对方私聊发一句简短自然的日常分享或问候{link_rule}"


def _beijing_now(now_ms: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(now_ms / 1000.0, tz=CST)


def is_within_active_hours(active_hours: str, now_ms: int) -> bool:
    """Check whether current Beijing time falls inside 'HH:MM-HH:MM'."""
    spec = active_hours.strip()
    if not spec or "-" not in spec:
        return True
    start_s, end_s = [p.strip() for p in spec.split("-", 1)]
    try:
        sh, sm = [int(x) for x in start_s.split(":", 1)]
        eh, em = [int(x) for x in end_s.split(":", 1)]
    except ValueError:
        return True
    dt = _beijing_now(now_ms)
    cur_m = dt.hour * 60 + dt.minute
    start_m, end_m = sh * 60 + sm, eh * 60 + em
    if start_m <= end_m:
        return start_m <= cur_m <= end_m
    return cur_m >= start_m or cur_m <= end_m


def _int_val(cfg: dict[str, str], key: str, default: int) -> int:
    try:
        return int(cfg.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _is_due(
    enabled: bool, per_day: int, interval_min: int,
    state: dict[str, str], prefix: str, *, now_ms: int,
) -> bool:
    if not enabled or per_day <= 0:
        return False
    today = _beijing_now(now_ms).strftime("%Y-%m-%d")
    day_cnt = _int_val(state, f"{prefix}_count", 0) if state.get(f"{prefix}_day") == today else 0
    if day_cnt >= per_day:
        return False
    last_ms = _int_val(state, f"{prefix}_last_ms", 0)
    if last_ms <= 0:
        return True
    phase = resolve_circadian_phase(now_ms)
    if phase.is_asleep:
        return False
    jitter = biological_jitter_factor(prefix, last_ms)
    eff_min = (interval_min / max(0.55, phase.proactive_multiplier)) * jitter
    return (now_ms - last_ms) >= int(eff_min * 60_000)


class QzoneMoodShowcaseScheduler:
    """Autonomously update QQ signature, post Qzone mood updates, and send proactive messages."""

    def __init__(
        self, *, caller: IOneBotApiCaller, llm: ILlmGateway,
        working_store: IWorkingStateStore, memory_reader: IMemoryReader,
        config_store: ISkillConfigStore, default_chat_key: str,
        sender: IMessageSender | None = None,
    ) -> None:
        self._caller, self._llm, self._working = caller, llm, working_store
        self._reader, self._cfg_store = memory_reader, config_store
        self._chat_key, self._sender = default_chat_key, sender

    async def _save_state_counter(
        self, prefix: str, state: dict[str, str], now_ms: int, text: str, inc: int = 1
    ) -> None:
        today = _beijing_now(now_ms).strftime("%Y-%m-%d")
        prev = _int_val(state, f"{prefix}_count", 0) if state.get(f"{prefix}_day") == today else 0
        await self._cfg_store.set_skill_config(
            QZONE_STATE_KEY,
            {
                f"{prefix}_day": today,
                f"{prefix}_count": str(prev + inc),
                f"{prefix}_last_ms": str(now_ms),
                f"{prefix}_last_text": text[:200],
            },
        )

    async def _recover_idle_energy_and_context(self, now_ms: int) -> tuple[str, float]:
        snap = await self._working.load_working_state("global")
        target_e = circadian_energy_target(now_ms)
        new_e = round(snap.affect.energy + (target_e - snap.affect.energy) * 0.25, 2)
        if abs(new_e - snap.affect.energy) >= 0.5:
            new_aff = snap.affect.model_copy(update={"energy": max(0.0, min(100.0, new_e))})
            snap = snap.model_copy(update={"affect": new_aff})
            await self._working.save_working_state(snap)
        params = await self._working.get_plastic_params()
        traits = await self._working.sync_persona_traits()
        cards = await self._reader.get_episodic_cards(self._chat_key)
        recent_mem = "；".join(c.summary for c in cards[-3:]) if cards else "日常待机"
        dt_str = _beijing_now(now_ms).strftime("%H:%M")
        ctx = (
            f"当前时间：{dt_str} ｜ 正在做：{snap.current_activity}\n"
            f"{synthesize_live_persona_directive(params, traits)}\n"
            f"最近发生的记忆摘要：{recent_mem}"
        )
        return ctx, snap.affect.energy

    async def _generate_and_set_signature(
        self, ctx_text: str, state: dict[str, str], now_ms: int, cfg: dict[str, str]
    ) -> str:
        prompt = (
            "请以第一人称写一句此刻的 QQ 个性签名（10~26字，口语自然，带一点当下心情或小动作，"
            "不要加引号，不要带任何群名或QQ号）。"
        )
        resp = await self._llm.complete(
            [{"role": "system", "content": ctx_text}, {"role": "user", "content": prompt}],
            temperature=0.85, max_tokens=budget(cfg, "token_budget_signature", 120),
            chat_key="qzone:signature", thinking_off=True,
        )
        sig = extract_content(resp)[:50]
        if not sig:
            return ""
        await self._caller.call_api("set_self_longnick", longNick=sig)
        await self._save_state_counter("sig", state, now_ms, sig)
        return sig

    async def _generate_and_post_qzone(
        self, ctx_text: str, state: dict[str, str], now_ms: int, cfg: dict[str, str]
    ) -> str:
        prompt = (
            "请以第一人称写一条发在自己 QQ 空间的日常说说（35~95字，像真人朋友一样自然碎碎念，"
            "可结合当下的时间、心情或最近发生的好玩小事，但不要出现具体群名和他人QQ号，不要加引号）。"
        )
        resp = await self._llm.complete(
            [{"role": "system", "content": ctx_text}, {"role": "user", "content": prompt}],
            temperature=0.85, max_tokens=budget(cfg, "token_budget_post", 400),
            chat_key="qzone:post", thinking_off=True,
        )
        post = extract_content(resp)[:280]
        if not post:
            return ""
        await self._caller.call_api("send_qzone_msg", content=post, ugc_right=1)
        await self._save_state_counter("qz", state, now_ms, post)
        return post

    async def _send_one_proactive_target(
        self, ctx_text: str, chat_key: str, at_uid: str | None,
        cfg: dict[str, str] | None = None,
    ) -> str:
        cfg = cfg or {}
        if self._sender is None:
            return ""
        prompt = _proactive_prompt_for(chat_key, at_uid)
        max_tok = budget(cfg, "token_budget_proactive", 300)
        resp = await self._llm.complete(
            [{"role": "system", "content": ctx_text}, {"role": "user", "content": prompt}],
            temperature=0.85, max_tokens=max_tok, chat_key=chat_key, thinking_off=True,
        )
        if is_truncated(resp):
            resp = await self._llm.complete(
                [{"role": "system", "content": ctx_text}, {"role": "user", "content": prompt}],
                temperature=0.85, max_tokens=max_tok + 200, chat_key=chat_key,
                thinking_off=True,
            )
        msg = extract_content(resp).strip()
        if not msg:
            return ""
        await self._sender.send_text(chat_key, (msg,), at_user_id=at_uid)
        return msg

    async def _generate_and_send_proactive(
        self, ctx_text: str, state: dict[str, str], cfg: dict[str, str], now_ms: int
    ) -> str:
        if self._sender is None:
            return ""
        targets = parse_proactive_targets(cfg.get("proactive_target", "private:10001001"))
        sent_msgs: list[str] = []
        for chat_key, at_uid in targets:
            msg = await self._send_one_proactive_target(ctx_text, chat_key, at_uid, cfg)
            if msg:
                sent_msgs.append(msg)
        if not sent_msgs:
            return ""
        snap = await self._working.load_working_state("global")
        if "B站" in snap.current_activity or "http" in snap.current_activity:
            await self._working.save_working_state(
                snap.model_copy(update={"current_activity": "戴着耳机边听歌边看群聊"})
            )
        joined = " | ".join(sent_msgs)
        await self._save_state_counter("pro", state, now_ms, joined, inc=len(sent_msgs))
        return joined

    async def run_tick(self, now_ms: int) -> dict[str, str]:
        """Check whether signature, Qzone post, or proactive chat is due and execute."""
        ctx_text, energy = await self._recover_idle_energy_and_context(now_ms)
        cfg = await self._cfg_store.get_skill_config(QZONE_CFG_KEY)
        if not is_within_active_hours(cfg.get("active_hours", "06:30-23:30"), now_ms):
            return {}
        state = await self._cfg_store.get_skill_config(QZONE_STATE_KEY)
        sig_due = _is_due(
            cfg.get("signature_enabled", "1") == "1",
            _int_val(cfg, "signature_per_day", 3),
            _int_val(cfg, "signature_interval_min", 240),
            state, "sig", now_ms=now_ms,
        )
        qz_due = _is_due(
            cfg.get("qzone_enabled", "1") == "1",
            _int_val(cfg, "qzone_per_day", 10),
            _int_val(cfg, "qzone_interval_min", 120),
            state, "qz", now_ms=now_ms,
        )
        pro_due = (energy >= 25.0) and _is_due(
            cfg.get("proactive_enabled", "1") == "1", 12,
            _int_val(cfg, "proactive_interval_min", 35),
            state, "pro", now_ms=now_ms,
        )
        return await self._dispatch_due_tasks(
            ctx_text, state, cfg, now_ms, (sig_due, qz_due, pro_due)
        )

    async def _dispatch_due_tasks(
        self, ctx_text: str, state: dict[str, str], cfg: dict[str, str],
        now_ms: int, flags: tuple[bool, bool, bool],
    ) -> dict[str, str]:
        sig_due, qz_due, pro_due = flags
        out: dict[str, str] = {}
        if sig_due:
            out["signature"] = await self._generate_and_set_signature(ctx_text, state, now_ms, cfg)
        if qz_due:
            out["qzone"] = await self._generate_and_post_qzone(ctx_text, state, now_ms, cfg)
        if pro_due:
            out["proactive"] = await self._generate_and_send_proactive(ctx_text, state, cfg, now_ms)
        return out
