"""M4.2 Concurrent Session Agent Runner with Tool Loop, Reply Rescue & Outcome Feedback."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from echomind.domain.models import Percept, TurnOutcome, TurnRecord, TurnStep
from echomind.domain.ports import (
    ICognitiveCoreFacade,
    ILlmGateway,
    IMessageSender,
    ITurnTraceStore,
)
from echomind.extensions.registry import ExtensionRegistry
from echomind.mind.ban_control import purge_message_batch
from echomind.runtime.prompt_composer import PromptComposer, StickerCandidate
from echomind.runtime.reply_rescue import rescue_unsent_reply
from echomind.runtime.working_scratchpad import WorkingScratchpad


def _extract_assistant_msg(raw_resp: dict[str, Any]) -> dict[str, Any]:
    choices = raw_resp.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    msg = first.get("message", {}) if isinstance(first, dict) else {}
    return msg if isinstance(msg, dict) else {}


def _parse_tool_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if not isinstance(raw_args, str):
        return {}
    try:
        parsed: dict[str, Any] = json.loads(raw_args)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _llm_step(resp: dict[str, Any], elapsed_ms: int, seq: int) -> TurnStep:
    usage = resp.get("usage")
    info = usage if isinstance(usage, dict) else {}
    prompt = int(info.get("prompt_tokens", 0) or 0)
    completion = int(info.get("completion_tokens", 0) or 0)
    details = info.get("prompt_tokens_details")
    cached = int(details.get("cached_tokens", 0) or 0) if isinstance(details, dict) else 0
    detail = f"{prompt}→{completion} tok" + (f"（缓存 {cached}）" if cached else "")
    out = str(_extract_assistant_msg(resp).get("content") or "").strip()[:300]
    return TurnStep(
        seq=seq, kind="llm", name=str(resp.get("model") or ""),
        detail=detail, output=out, elapsed_ms=elapsed_ms,
    )


def _tool_step(
    name: str, args: dict[str, Any], result_str: str, elapsed_ms: int, seq: int
) -> TurnStep:
    snippet = json.dumps(args, ensure_ascii=False)[:240]
    return TurnStep(
        seq=seq, kind="tool", name=name, detail=snippet,
        output=result_str[:300], elapsed_ms=elapsed_ms,
    )


def _tool_reply(tc: dict[str, Any], name: str, content: str) -> dict[str, Any]:
    return {
        "role": "tool", "tool_call_id": str(tc.get("id", "call_1")),
        "name": name, "content": content,
    }


def _init_running_record(
    sid: str, chat_key: str, now_ms: int, triggers: tuple[Percept, ...], ctx_n: int,
    *, sys_p: str = "", usr_p: str = "",
) -> TurnRecord:
    trig = f"{triggers[-1].sender_name}：{triggers[-1].text[:40]}" if triggers else ""
    return TurnRecord(
        turn_id=sid, chat_key=chat_key, ts=now_ms, trigger=trig, status="running",
        context_count=ctx_n, trigger_count=len(triggers), system_prompt=sys_p, user_prompt=usr_p,
    )


class AgentSessionRunner:
    """Execute a complete cognitive turn and feed TurnOutcome back to ICognitiveCoreFacade."""

    def __init__(
        self, cognitive: ICognitiveCoreFacade, llm: ILlmGateway, registry: ExtensionRegistry,
        sender: IMessageSender, composer: PromptComposer, *,
        temperature: float = 0.6, trace_store: ITurnTraceStore | None = None,
        event_bus: Any = None,
    ) -> None:
        self._cognitive, self._llm, self._registry = cognitive, llm, registry
        self._sender, self._composer, self._traces = sender, composer, trace_store
        self._bus = event_bus
        self._scratchpad = WorkingScratchpad()
        self._active_bans: tuple[str, ...] = ()
        self._temperature = temperature
        self._turn_counts: dict[str, int] = {}

    async def _sync_running_trace(
        self, base_rec: TurnRecord, steps: list[TurnStep], sent_count: int, t_turn: float
    ) -> None:
        if self._traces is None:
            return
        models = [s.name for s in steps if s.kind == "llm" and s.name]
        rec = base_rec.model_copy(
            update={
                "rounds": len(models), "sent_count": sent_count,
                "total_ms": int((time.monotonic() - t_turn) * 1000),
                "model": models[-1] if models else "", "steps": tuple(steps),
            }
        )
        await self._traces.save_turn(rec)

    def _prepare_voice_args(
        self, name: str, args: dict[str, Any], sent_texts: list[str]
    ) -> tuple[dict[str, Any] | None, str]:
        if name == "feiyu_say":
            if sent_texts:
                return None, "本轮已发送过文字或语音回复，请勿重复再用语音念一遍，直接结束即可。"
            kept = purge_message_batch(str(args.get("text", "")), self._active_bans)
            if not kept:
                return None, "已拦截：语音内容命中主人禁用词，未发送"
            sent_texts.append(kept[0])
            return {**args, "text": kept[0]}, ""
        if name == "feiyu_cover":
            sent_texts.append(f"[翻唱:{args.get('song', '')}]")
        return args, ""

    def _prepare_outbound_args(
        self, name: str, args: dict[str, Any], sent_texts: list[str]
    ) -> tuple[dict[str, Any] | None, str]:
        if name != "send_message":
            return self._prepare_voice_args(name, args, sent_texts)
        if sent_texts:
            return None, "本轮已发送过文字消息，请勿重复连发，直接结束即可。"
        kept = purge_message_batch(args.get("messages", []), self._active_bans)
        if not kept:
            return None, "已拦截：全部内容命中主人禁用词，未发送"
        sent_texts.extend(kept)
        return {**args, "messages": list(kept)}, ""

    async def _execute_single_tool_call(
        self, chat_key: str, tc: dict[str, Any],
        tools_used: list[str], sent_texts: list[str], *, steps: list[TurnStep],
    ) -> dict[str, Any]:
        fn = tc.get("function", {})
        name = str(fn.get("name", "")) if isinstance(fn, dict) else ""
        raw_args = _parse_tool_args(fn.get("arguments") if isinstance(fn, dict) else "{}")
        eff_args, block_msg = self._prepare_outbound_args(name, raw_args, sent_texts)
        if eff_args is None:
            return _tool_reply(tc, name, block_msg)
        tools_used.append(name)
        t_tool = time.monotonic()
        result_str = await self._registry.execute_tool(name, chat_key, eff_args)
        tool_ms = int((time.monotonic() - t_tool) * 1000)
        self._scratchpad.record_tool_finding(chat_key, name, result_str, int(time.time() * 1000))
        steps.append(_tool_step(name, eff_args, result_str, tool_ms, len(steps) + 1))
        return _tool_reply(tc, name, result_str)

    async def _execute_tool_batch(
        self, chat_key: str, raw_calls: list[Any], tools_used: list[str],
        sent_texts: list[str], messages: list[dict[str, Any]], *, steps: list[TurnStep],
    ) -> None:
        for tc in (c for c in raw_calls if isinstance(c, dict)):
            tool_msg = await self._execute_single_tool_call(
                chat_key, tc, tools_used, sent_texts, steps=steps
            )
            messages.append(tool_msg)

    async def _run_tool_loop(
        self, chat_key: str, messages: list[dict[str, Any]],
        steps: list[TurnStep], max_rounds: int = 6, *,
        base_rec: TurnRecord | None = None, t_turn: float = 0.0,
        selected_tools: tuple[str, ...] = (), turn_temp: float | None = None,
    ) -> tuple[list[str], list[str], str]:
        tools_schema = self._registry.export_openai_tools(selected_tools)
        eff_temp = turn_temp if turn_temp is not None else self._temperature
        tools_used: list[str] = []
        sent_texts: list[str] = []
        last_content = ""
        for _ in range(max_rounds):
            t_llm = time.monotonic()
            resp = await self._llm.complete(
                messages, tools=tools_schema or None, temperature=eff_temp, chat_key=chat_key,
            )
            steps.append(_llm_step(resp, int((time.monotonic() - t_llm) * 1000), len(steps) + 1))
            if base_rec is not None:
                await self._sync_running_trace(base_rec, steps, len(sent_texts), t_turn)
            msg = _extract_assistant_msg(resp)
            last_content = str(msg.get("content") or "")
            raw_calls = msg.get("tool_calls")
            if not isinstance(raw_calls, list) or not raw_calls:
                break
            messages.append(msg)
            await self._execute_tool_batch(
                chat_key, raw_calls, tools_used, sent_texts, messages, steps=steps
            )
            if base_rec is not None:
                await self._sync_running_trace(base_rec, steps, len(sent_texts), t_turn)
        return sent_texts, tools_used, last_content

    async def _maybe_rescue_reply(
        self, chat_key: str, last_content: str,
        sent_texts: list[str], tools_used: list[str], steps: list[TurnStep],
    ) -> None:
        if sent_texts or (
            {"send_sticker", "feiyu_say", "feiyu_cover", "send_poke"} & set(tools_used)
        ):
            return
        rescued = rescue_unsent_reply(last_content)
        if not rescued:
            return
        purged = purge_message_batch((rescued,), self._active_bans)
        if not purged:
            return
        await self._sender.send_text(chat_key, (purged[0],))
        sent_texts.append(purged[0])
        steps.append(TurnStep(seq=len(steps) + 1, kind="tool", name="send_message(rescue)"))

    async def _compose_with_facets(
        self, chat_key: str, frame: Any, read_history: tuple[Percept, ...],
        unread_triggers: tuple[Percept, ...], *,
        stickers: tuple[StickerCandidate, ...], now_ms: int,
    ) -> tuple[list[dict[str, Any]], str, str]:
        messages = self._composer.compose(
            frame, read_history, unread_triggers, stickers=stickers, now_ms=now_ms
        )
        facets = [await f.render_prompt_line(chat_key) for f in self._registry.facets]
        cont = self._scratchpad.render_continuity_block(chat_key, now_ms)
        extra = [x for x in (*facets, cont) if x]
        if extra and messages:
            messages[0]["content"] = f"{messages[0].get('content', '')}\n" + "\n".join(extra)
        sys_p = str(messages[0].get("content", "")) if messages else ""
        usr_p = str(messages[1].get("content", "")) if len(messages) > 1 else ""
        return messages, sys_p, usr_p

    async def run_turn(
        self, chat_key: str, read_history: tuple[Percept, ...],
        unread_triggers: tuple[Percept, ...], *,
        stickers: tuple[StickerCandidate, ...] = (), social_reward: float = 0.4,
    ) -> TurnOutcome:
        t_turn, now_ms, sid = time.monotonic(), int(time.time() * 1000), uuid.uuid4().hex[:12]
        steps: list[TurnStep] = []
        frame = await self._cognitive.build_cognitive_frame(chat_key, unread_triggers)
        self._active_bans = frame.banned_phrases
        messages, sys_p, usr_p = await self._compose_with_facets(
            chat_key, frame, read_history, unread_triggers, stickers=stickers, now_ms=now_ms
        )
        base_rec = _init_running_record(
            sid, chat_key, now_ms, unread_triggers, len(read_history), sys_p=sys_p, usr_p=usr_p
        )
        await self._sync_running_trace(base_rec, steps, 0, t_turn)
        core = frame.cybernetic_core
        sent_texts, tools_used, last_content = await self._run_tool_loop(
            chat_key, messages, steps, base_rec=base_rec, t_turn=t_turn,
            selected_tools=core.selected_tools, turn_temp=core.recommended_temperature,
        )
        await self._maybe_rescue_reply(chat_key, last_content, sent_texts, tools_used, steps)
        self._scratchpad.record_self_reply(chat_key, tuple(sent_texts), now_ms)
        conflict = any("元认知防忽悠警报" in w for w in frame.epistemic_warnings)
        outcome = TurnOutcome(
            session_id=sid, chat_key=chat_key, triggers=unread_triggers,
            sent_texts=tuple(sent_texts), tools_used=tuple(tools_used),
            social_reward=social_reward, epistemic_conflict_detected=conflict,
            steps=tuple(steps), total_ms=int((time.monotonic() - t_turn) * 1000),
            context_count=len(read_history), system_prompt=sys_p, user_prompt=usr_p,
        )
        await self._cognitive.on_turn_completed(outcome)
        if self._bus is not None:
            await self._bus.publish(outcome)
        await self._maybe_consolidate_batch(chat_key, read_history, unread_triggers, outcome)
        return outcome

    async def _maybe_consolidate_batch(
        self,
        chat_key: str,
        read_history: tuple[Percept, ...],
        unread_triggers: tuple[Percept, ...],
        outcome: TurnOutcome,
    ) -> None:
        cnt = self._turn_counts.get(chat_key, 0) + 1
        self._turn_counts[chat_key] = cnt
        if cnt % 6 != 0 or not outcome.sent_texts:
            return
        lines = tuple(
            f"{p.sender_name}(QQ:{p.sender_id}): {p.text}"
            for p in (*read_history[-12:], *unread_triggers)
        ) + tuple(f"回音(我): {s}" for s in outcome.sent_texts)
        _, role_text = self._composer.role_card()
        await self._cognitive.consolidate_dialogue_batch(
            chat_key, lines, self._llm, role_text=role_text
        )
