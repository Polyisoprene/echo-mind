"""M3.4/M3.5 CognitiveCoreFacade: Single entry point exposed to Runtime (Law of Demeter)."""

from __future__ import annotations

import time
from typing import Any, Literal

from echomind.domain.models import (
    AttentionDecision,
    CognitiveFrame,
    Percept,
    ProactiveProposal,
    RecalledMemoryItem,
    SemanticFact,
    SocialBondProfile,
    TurnOutcome,
    TurnRecord,
    WorkingSnapshot,
)
from echomind.domain.ports import (
    ILlmGateway,
    IMemoryReader,
    IMemoryWriter,
    IPersonaConstraintStore,
    ITurnTraceStore,
    IWorkingStateStore,
)
from echomind.mind.ban_control import extract_new_bans
from echomind.mind.circadian import record_gate_decision
from echomind.mind.cybernetics import (
    compute_cybernetic_core,
    consume_proposal_snapshot,
    render_cybernetic_core_directive,
)
from echomind.mind.drives import apply_temporal_decay_and_circadian, apply_turn_affect_and_drives
from echomind.mind.ebbinghaus import (
    extract_mentioned_uids,
    recall_episodic_memories,
    select_relevant_facts,
)
from echomind.mind.epistemic import EpistemicCalibrator
from echomind.mind.explorer import arbitrate_autonomous_action
from echomind.mind.frame_renderer import (
    build_curiosity_prompts,
    match_active_rules,
    render_mind_block,
)
from echomind.mind.memory_consolidator import (
    consolidate_turn_memory,
    run_hippocampal_batch_consolidation,
)
from echomind.mind.perceptual_gate import PerceptualGate
from echomind.mind.personality import synthesize_live_persona_directive
from echomind.mind.plasticity import NeuroplasticityEngine
from echomind.mind.salience_hydraulics import apply_speaking_satiation
from echomind.mind.shadow_appraisal import (
    ShadowAppraisalResult,
    evaluate_shadow_appraisal,
    filter_unfulfilled_intentions,
)


def _trigger_label(outcome: TurnOutcome) -> str:
    last = outcome.triggers[-1] if outcome.triggers else None
    return f"{last.sender_name}：{last.text[:40]}" if last else ""


class CognitiveCoreFacade:
    """Unified 12-Layer Cognitive Core Facade satisfying ICognitiveCoreFacade."""

    def __init__(
        self, mem_reader: IMemoryReader, mem_writer: IMemoryWriter,
        working_store: IWorkingStateStore, owner_qq: str = "",
        default_group_key: str = "group:10002002", *,
        constraint_store: IPersonaConstraintStore | None = None,
        trace_store: ITurnTraceStore | None = None,
    ) -> None:
        self._reader, self._writer, self._working = mem_reader, mem_writer, working_store
        self._owner_qq, self._default_group = owner_qq, default_group_key
        self._gate, self._calibrator = PerceptualGate(), EpistemicCalibrator()
        self._constraints, self._traces = constraint_store, trace_store
        self._plasticity = NeuroplasticityEngine(working_store)
        self._last_active_ms: int = int(time.time() * 1000)
        self._gate_log: list[dict[str, Any]] = []

    @property
    def owner_qq(self) -> str:
        return self._owner_qq

    @property
    def last_active_ms(self) -> int:
        return self._last_active_ms

    @property
    def recent_gate_log(self) -> list[dict[str, Any]]:
        return list(reversed(self._gate_log))

    async def evaluate_incoming(
        self, percept: Percept, *, dry_run: bool = False
    ) -> AttentionDecision:
        if not dry_run:
            self._last_active_ms = max(self._last_active_ms, percept.timestamp_ms)
        snap = await self._working.load_working_state("global")
        params = await self._working.get_plastic_params()
        talk = params["talkativeness"].value if "talkativeness" in params else 58.0
        facts = await self._reader.get_semantic_facts(percept.chat_key)
        rivals = await self._reader.get_rival_names(percept.chat_key)
        vocab = frozenset(f.subject.lower() for f in facts)
        dec = self._gate.evaluate(
            percept, snap, vocab, rivals, talkativeness=talk,
            record_state=not dry_run, owner_qq=self._owner_qq, params=params,
        )
        if not dry_run:
            self._gate_log = record_gate_decision(self._gate_log, percept, dec)
        return dec

    async def _load_bonds_map(
        self, chat_key: str, uids: tuple[str, ...]
    ) -> dict[str, SocialBondProfile]:
        items = [(u, await self._reader.get_social_bond(chat_key, u)) for u in uids]
        return {u: b for u, b in items if b is not None}

    async def _recall_and_reinforce(
        self, chat_key: str, triggers: tuple[Percept, ...], uids: tuple[str, ...],
        now_ms: int, *, dry_run: bool = False,
    ) -> tuple[RecalledMemoryItem, ...]:
        cards = await self._reader.get_episodic_cards(chat_key)
        q_str = " ".join(p.text for p in triggers)
        recalled = recall_episodic_memories(cards, q_str, uids, now_ms, top_k=8)
        if not dry_run:
            for r_item in recalled:
                await self._writer.reinforce_episodic_card(r_item.card.card_id, now_ms)
        return recalled

    def _maybe_impose_cold_shoulder(
        self, chat_key: str, new_irr: float, triggers: tuple[Percept, ...]
    ) -> None:
        if new_irr > 85.0 and triggers and triggers[-1].sender_id != self._owner_qq:
            last = triggers[-1]
            self._gate.impose_cold_shoulder(chat_key, last.sender_id, last.timestamp_ms)

    async def _apply_shadow_and_save(
        self, chat_key: str, base_snap: WorkingSnapshot, triggers: tuple[Percept, ...],
        bonds_map: dict[str, SocialBondProfile], *, dry_run: bool = False,
    ) -> tuple[WorkingSnapshot, ShadowAppraisalResult, str]:
        params = await self._working.get_plastic_params()
        traits = await self._working.sync_persona_traits()
        shadow = evaluate_shadow_appraisal(
            triggers, base_snap.affect, params, traits, bonds_map, owner_qq=self._owner_qq
        )
        raw_irr = base_snap.affect.irritation + shadow.irritation_delta
        new_irr = max(0.0, min(100.0, round(raw_irr, 2)))
        updated = base_snap.model_copy(
            update={"affect": base_snap.affect.model_copy(update={"irritation": new_irr})}
        )
        if not dry_run:
            await self._working.save_working_state(updated)
            self._maybe_impose_cold_shoulder(chat_key, new_irr, triggers)
        return updated, shadow, synthesize_live_persona_directive(params, traits)

    async def _advance_working_state(
        self, chat_key: str, triggers: tuple[Percept, ...], facts: tuple[SemanticFact, ...]
    ) -> tuple[WorkingSnapshot, AttentionDecision | None, float]:
        snap = await self._working.load_working_state("global")
        params = await self._working.get_plastic_params()
        skep = params["skepticism"].value if "skepticism" in params else 55.0
        talk = params["talkativeness"].value if "talkativeness" in params else 58.0
        cur_rate = params["curiosity_rate"].value if "curiosity_rate" in params else 65.0
        rivals = await self._reader.get_rival_names(chat_key)
        vocab = frozenset(f.subject.lower() for f in facts)
        last_dec = (
            self._gate.evaluate(
                triggers[-1], snap, vocab, rivals, talkativeness=talk,
                record_state=False, owner_qq=self._owner_qq, params=params,
            )
            if triggers else None
        )
        unknowns = last_dec.detected_unknown_terms if last_dec else ()
        updated = apply_turn_affect_and_drives(
            snap, triggers, self._owner_qq, rivals, unknowns, curiosity_rate=cur_rate
        )
        return updated, last_dec, skep

    async def _resolve_bans(
        self, triggers: tuple[Percept, ...], *, dry_run: bool = False
    ) -> tuple[str, ...]:
        if self._constraints is None:
            return ()
        new_bans = extract_new_bans(triggers, self._owner_qq)
        if dry_run:
            existing = await self._constraints.get_banned_phrases()
            return tuple(dict.fromkeys([*new_bans, *existing]))
        for phrase in new_bans:
            await self._constraints.add_banned_phrase(phrase, "主人明令禁止的口癖")
        return await self._constraints.get_banned_phrases()

    async def build_cognitive_frame(
        self, chat_key: str, triggers: tuple[Percept, ...], *, dry_run: bool = False
    ) -> CognitiveFrame:
        now_ms = int(time.time() * 1000)
        scene: Literal["group", "private"] = "private" if "private:" in chat_key else "group"
        facts = await self._reader.get_semantic_facts(chat_key)
        base_snap, last_dec, skep = await self._advance_working_state(chat_key, triggers, facts)
        bans = await self._resolve_bans(triggers, dry_run=dry_run)
        uids = extract_mentioned_uids(triggers, facts)
        bonds_map = await self._load_bonds_map(chat_key, uids)
        updated_snap, shadow, persona_block = await self._apply_shadow_and_save(
            chat_key, base_snap, triggers, bonds_map, dry_run=dry_run
        )
        warnings, _ = self._calibrator.calibrate(triggers, facts, bonds_map, skepticism=skep)
        rules = await self._reader.get_procedural_rules(chat_key)
        recalled = await self._recall_and_reinforce(
            chat_key, triggers, uids, now_ms, dry_run=dry_run
        )
        cur_prompts = build_curiosity_prompts(triggers, last_dec, updated_snap.affect)
        unk_terms = last_dec.detected_unknown_terms if last_dec else ()
        cyber_core = compute_cybernetic_core(
            scene, updated_snap, triggers, bonds_map,
            owner_qq=self._owner_qq, unknown_terms=unk_terms, warnings=warnings,
        )
        rel_facts = select_relevant_facts(facts, " ".join(p.text for p in triggers), limit=28)
        r_lines = match_active_rules(rules, triggers)
        core_blk = render_mind_block(
            scene, updated_snap, bonds=bonds_map, facts=rel_facts, warnings=warnings,
            shadow_directives=shadow.shadow_directives, rule_lines=r_lines,
            recalled=recalled, cur_prompts=cur_prompts, bans=bans,
        )
        cyber_line = render_cybernetic_core_directive(cyber_core)
        return CognitiveFrame(
            chat_key=chat_key, scene=scene, must_reply=bool(last_dec and last_dec.tier == 1),
            affect=updated_snap.affect, drives=updated_snap.drives,
            rendered_mind_block=f"{core_blk}\n{cyber_line}\n{persona_block}",
            epistemic_warnings=(*warnings, *shadow.shadow_directives),
            curiosity_prompts=cur_prompts, banned_phrases=bans, cybernetic_core=cyber_core,
        )

    async def _persist_turn(self, outcome: TurnOutcome, now_ms: int) -> None:
        if self._traces is None or not outcome.steps:
            return
        models = [s.name for s in outcome.steps if s.kind == "llm" and s.name]
        rec = TurnRecord(
            turn_id=outcome.session_id, chat_key=outcome.chat_key, ts=now_ms,
            trigger=_trigger_label(outcome), status=outcome.status, rounds=len(models),
            sent_count=len(outcome.sent_texts), total_ms=outcome.total_ms,
            model=models[-1] if models else "", context_count=outcome.context_count,
            trigger_count=len(outcome.triggers), system_prompt=outcome.system_prompt,
            user_prompt=outcome.user_prompt, steps=outcome.steps,
        )
        await self._traces.save_turn(rec)

    async def on_turn_completed(self, outcome: TurnOutcome) -> None:
        now_ms = int(time.time() * 1000)
        if outcome.sent_texts:
            self._gate.mark_bot_spoke(outcome.chat_key, outcome.sent_texts, now_ms)
            for p in outcome.triggers:
                self._gate.mark_replied_to(outcome.chat_key, p.sender_id, now_ms)
            snap = await self._working.load_working_state("global")
            rem = filter_unfulfilled_intentions(snap.intentions, outcome.sent_texts, now_ms)
            satiated = apply_speaking_satiation(
                snap.model_copy(update={"intentions": rem}), outcome.sent_texts, outcome.tools_used
            )
            await self._working.save_working_state(satiated)
        await self._persist_turn(outcome, now_ms)
        await consolidate_turn_memory(self._reader, self._writer, outcome, now_ms, self._owner_qq)
        await self._plasticity.adapt_from_outcome(outcome)

    async def _consume_proposal_state(
        self, snap: WorkingSnapshot, proposal: ProactiveProposal, now_ms: int
    ) -> None:
        self._last_active_ms = max(self._last_active_ms, now_ms)
        await self._working.save_working_state(consume_proposal_snapshot(snap, proposal))

    async def run_autonomous_tick(self, now_ms: int) -> ProactiveProposal | None:
        raw_snap = await self._working.load_working_state("global")
        params = await self._working.get_plastic_params()
        idle_target = params["proactive_idle_min"].value if "proactive_idle_min" in params else 10.0
        idle_min = max(0.0, (now_ms - self._last_active_ms) / 60_000.0)
        priv_key = f"private:{self._owner_qq}" if self._owner_qq else ""
        proposal = arbitrate_autonomous_action(
            raw_snap, self._default_group, priv_key, idle_min,
            proactive_idle_min=idle_target, now_ms=now_ms,
        )
        if proposal is not None:
            await self._consume_proposal_state(raw_snap, proposal, now_ms)
            return proposal
        drifted = apply_temporal_decay_and_circadian(raw_snap, min(idle_min, 30.0), now_ms)
        if drifted != raw_snap:
            await self._working.save_working_state(drifted)
        return None

    async def consolidate_dialogue_batch(
        self, chat_key: str, transcript_lines: tuple[str, ...],
        llm: ILlmGateway, *, role_text: str = "",
    ) -> int:
        now_ms = int(time.time() * 1000)
        return await run_hippocampal_batch_consolidation(
            chat_key, self._reader, self._writer, llm,
            transcript_lines, now_ms=now_ms, working_store=self._working, role_text=role_text,
        )
