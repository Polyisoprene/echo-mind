"""M6.1/M13.2 Cognitive Heartbeat, Novelty-Deduplicated Surfing & Exogenous Affect Scheduler."""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    ProactiveProposal,
    SemanticFact,
    TurnRecord,
    TurnStep,
)
from echomind.domain.ports import (
    IAsyncSqlStore,
    ICognitiveCoreFacade,
    ILlmGateway,
    IMemoryReader,
    IMemoryWriter,
    IMessageSender,
    ITurnTraceStore,
    IWorkingStateStore,
)
from echomind.extensions.registry import ExtensionRegistry
from echomind.mind.drives import apply_exogenous_surf_affect
from echomind.mind.plasticity import NeuroplasticityEngine
from echomind.mind.shadow_appraisal import should_prune_card

BV_ID_RE = re.compile(r"BV[0-9A-Za-z]{10}")
TITLE_BOOK_RE = re.compile(r"《([^》]{2,40})》")


def _extract_llm_reply(resp: dict[str, Any]) -> str:
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    msg = first.get("message")
    raw = str(msg.get("content") or "") if isinstance(msg, dict) else ""
    return raw.strip().strip('"“”')[:160]


def _surf_tool_for(proposal: ProactiveProposal) -> tuple[str, dict[str, Any]]:
    if proposal.drive_kind == "curiosity_explore":
        return "web_search", {"query": proposal.topic_hint or "网络热梗"}
    if proposal.drive_kind in ("bili_surf", "cold_group_topic"):
        return "bili_popular", {"limit": 10}
    return "", {}


def _extract_keys(text: str) -> set[str]:
    return {*BV_ID_RE.findall(text), *TITLE_BOOK_RE.findall(text)}


def _pick_unseen_bullet_line(finding: str, seen_keys: set[str]) -> str:
    fallback = ""
    for ln in finding.splitlines():
        s = ln.strip()
        if not s.startswith("-"):
            continue
        clean = s.lstrip("- ").strip()
        if not fallback:
            fallback = clean
        line_keys = _extract_keys(clean)
        if not line_keys or not (line_keys & seen_keys):
            return clean
    return ""


class CognitiveHeartbeatScheduler:
    """Coordinate autonomous curiosity ticks, due reminders, and CraniMem sleep pruning."""

    def __init__(
        self, db: IAsyncSqlStore, mem_reader: IMemoryReader,
        cognitive: ICognitiveCoreFacade, sender: IMessageSender, *,
        qzone_scheduler: Any = None, registry: ExtensionRegistry | None = None,
        mem_writer: IMemoryWriter | None = None,
        working_store: IWorkingStateStore | None = None,
        trace_store: ITurnTraceStore | None = None, llm: ILlmGateway | None = None,
    ) -> None:
        self._db, self._reader, self._cognitive = db, mem_reader, cognitive
        self._sender, self._qzone, self._registry = sender, qzone_scheduler, registry
        self._writer, self._working, self._traces = mem_writer, working_store, trace_store
        self._llm = llm

    async def _load_seen_keys(self) -> set[str]:
        sql_m = "SELECT text FROM chat_messages WHERE is_self = 1 ORDER BY id DESC LIMIT 40"
        sql_e = "SELECT finding_summary FROM exploration_logs ORDER BY id DESC LIMIT 25"
        keys: set[str] = set()
        async with self._db.connect() as conn:
            for r in await (await conn.execute(sql_m)).fetchall():
                keys.update(_extract_keys(str(r[0])))
            for r in await (await conn.execute(sql_e)).fetchall():
                keys.update(_extract_keys(str(r[0])))
        return keys

    async def check_due_reminders(self, now_ms: int) -> tuple[int, ...]:
        """Fire all due, unfired reminders in SQLite and mark them fired=1."""
        sql_sel = (
            "SELECT id, chat_key, target_user_id, content FROM reminders "
            "WHERE fired = 0 AND remind_at_ms <= ? ORDER BY remind_at_ms ASC LIMIT 10"
        )
        async with self._db.connect() as conn:
            rows = list(await (await conn.execute(sql_sel, (now_ms,))).fetchall())
        fired_ids: list[int] = []
        for row in rows:
            rem_id, chat_key = int(row[0]), str(row[1])
            target_uid = str(row[2]).strip() or None
            await self._sender.send_text(
                chat_key, (f"⏰ [定时提醒] {row[3]}",), at_user_id=target_uid
            )
            fired_ids.append(rem_id)
        if not fired_ids:
            return ()
        async with self._db.connect() as conn:
            for rid in fired_ids:
                await conn.execute("UPDATE reminders SET fired = 1 WHERE id = ?", (rid,))
            await conn.commit()
        return tuple(fired_ids)

    async def run_sleep_pruning(self, chat_key: str, now_ms: int) -> tuple[int, ...]:
        """CraniMem (Mody et al., 2026) sleep consolidation: prune decayed cards & stale traits."""
        if self._working is not None:
            await self._working.sync_persona_traits()
        cutoff = now_ms - 86_400_000
        async with self._db.connect() as conn:
            sql_f = (
                "DELETE FROM semantic_facts WHERE is_locked = 0 AND source = 'peer' "
                "AND revision_count <= 1 AND confidence < 0.65 "
                "AND updated_at > 0 AND updated_at < ?"
            )
            await conn.execute(sql_f, (cutoff,))
            await conn.commit()
        cards = await self._reader.get_episodic_cards(chat_key)
        to_prune = [c.card_id for c in cards if should_prune_card(c, now_ms)]
        if not to_prune:
            return ()
        async with self._db.connect() as conn:
            for cid in to_prune:
                await conn.execute("DELETE FROM episodic_memories WHERE id = ?", (cid,))
            await conn.commit()
        return tuple(to_prune)

    async def _speak_proposal(
        self, proposal: ProactiveProposal, unseen_line: str, steps: list[TurnStep]
    ) -> str:
        if self._llm is None or proposal.drive_kind == "bili_surf":
            return ""
        if proposal.drive_kind in ("curiosity_explore", "cold_group_topic") and not unseen_line:
            return ""
        t0 = time.monotonic()
        ctx = f"\n【全新未分享过的内容】\n{unseen_line}" if unseen_line else ""
        prompt = (
            f"{proposal.goal_instruction}{ctx}\n"
            "请以回音的自然口吻写出要发到聊天里的那句话（若分享了上面视频，"
            "必须附上完整的 https://www.bilibili.com/video/BV... 链接！只输出话本身，不要加引号）。"
        )
        try:
            resp = await self._llm.complete(
                [{"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=140, chat_key=proposal.chat_key,
            )
        except Exception:
            return ""
        spoken = _extract_llm_reply(resp)
        if not spoken:
            return ""
        await self._sender.send_text(proposal.chat_key, (spoken,))
        ms = int((time.monotonic() - t0) * 1000)
        steps.append(
            TurnStep(
                seq=len(steps) + 1, kind="tool", name="send_message",
                detail=spoken, elapsed_ms=ms,
            )
        )
        return spoken

    async def _execute_autonomous_surf(
        self, proposal: ProactiveProposal, now_ms: int
    ) -> str:
        t0 = time.monotonic()
        steps: list[TurnStep] = []
        t_name, t_args = _surf_tool_for(proposal)
        finding, unseen_line = "", ""
        if self._registry is not None and t_name:
            seen_keys = await self._load_seen_keys()
            finding = await self._registry.execute_tool(t_name, proposal.chat_key, t_args)
            unseen_line = _pick_unseen_bullet_line(finding, seen_keys)
            t_ms = int((time.monotonic() - t0) * 1000)
            steps.append(
                TurnStep(
                    seq=1, kind="tool", name=t_name, detail=str(t_args),
                    output=(unseen_line or finding)[:300], elapsed_ms=t_ms,
                )
            )
        spoken = await self._speak_proposal(proposal, unseen_line, steps)
        total_ms = int((time.monotonic() - t0) * 1000)
        await self._save_surf_memory_and_trace(
            proposal, unseen_line, spoken, steps=tuple(steps), elapsed=total_ms, now_ms=now_ms
        )
        if unseen_line and spoken:
            return f"🆕 新发现：{unseen_line}\n💬 已主动发言：{spoken}"
        if unseen_line:
            return f"🆕 静默冲浪吸收新内容：{unseen_line}"
        if spoken:
            return f"💬 已主动发言：{spoken}"
        return finding[:200] if finding else proposal.goal_instruction

    async def _update_surf_mind(
        self, proposal: ProactiveProposal, unseen_line: str, spoken: str
    ) -> None:
        if self._writer is not None and unseen_line:
            fact = SemanticFact(
                chat_key="global", subject=f"最近B站冲浪:{proposal.topic_hint[:18]}",
                fact_text=unseen_line[:160], confidence=0.88, source="explored",
            )
            await self._writer.upsert_semantic_fact(fact)
        if self._working is None:
            return
        if unseen_line or spoken:
            snap = await self._working.load_working_state("global")
            updated = apply_exogenous_surf_affect(snap, unseen_line, shared_to_chat=bool(spoken))
            await self._working.save_working_state(updated)
        if unseen_line:
            await NeuroplasticityEngine(self._working).adapt_from_exogenous_info(
                proposal.drive_kind, unseen_line
            )

    async def _save_surf_memory_and_trace(
        self,
        proposal: ProactiveProposal,
        unseen_line: str,
        spoken: str,
        *,
        steps: tuple[TurnStep, ...],
        elapsed: int,
        now_ms: int,
    ) -> None:
        await self._update_surf_mind(proposal, unseen_line, spoken)
        if self._traces is None or not steps:
            return
        lbl = proposal.topic_hint if proposal.topic_hint else proposal.drive_kind
        trig = f"🔭 [自主行动/{proposal.drive_kind}] {lbl}"
        cnt = 1 if spoken else 0
        rec = TurnRecord(
            turn_id=f"surf_{uuid.uuid4().hex[:8]}", chat_key=proposal.chat_key, ts=now_ms,
            trigger=trig, status="done", rounds=cnt, sent_count=cnt,
            total_ms=elapsed, model="AutonomousExplorer", steps=steps,
        )
        await self._traces.save_turn(rec)

    async def execute_proposal(self, proposal: ProactiveProposal, now_ms: int) -> str:
        """Execute one autonomous exploration/surf/proactive proposal and persist its log."""
        summary = await self._execute_autonomous_surf(proposal, now_ms)
        sql = (
            "INSERT INTO exploration_logs "
            "(ts, kind, topic, finding_summary, spoke_chat_key) VALUES (?, ?, ?, ?, ?)"
        )
        topic = proposal.topic_hint or proposal.drive_kind
        params = (now_ms, proposal.drive_kind, topic, summary, proposal.chat_key)
        async with self._db.connect() as conn:
            await conn.execute(sql, params)
            await conn.commit()
        return summary

    async def _poll_custom_proposers(self, chat_key: str) -> ProactiveProposal | None:
        if self._registry is None or not self._registry.proposers:
            return None
        aff, drv = AffectiveVector(), DriveState()
        if self._working is not None:
            snap = await self._working.load_working_state("global")
            aff, drv = snap.affect, snap.drives
        for ext_prop in self._registry.proposers:
            proposal = await ext_prop.propose(chat_key, aff, drv)
            if proposal is not None:
                return proposal
        return None

    async def run_heartbeat_cycle(
        self, chat_key: str, now_ms: int
    ) -> tuple[ProactiveProposal | None, tuple[int, ...], tuple[int, ...]]:
        """Execute one complete autonomous cycle: due reminders + sleep pruning + drive tick."""
        fired = await self.check_due_reminders(now_ms)
        pruned = await self.run_sleep_pruning(chat_key, now_ms)
        if self._qzone is not None:
            await self._qzone.run_tick(now_ms)
        proposal = await self._cognitive.run_autonomous_tick(now_ms)
        if proposal is None:
            proposal = await self._poll_custom_proposers(chat_key)
        if proposal is not None:
            await self.execute_proposal(proposal, now_ms)
        return proposal, fired, pruned
