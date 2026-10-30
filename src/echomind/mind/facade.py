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
    WorkingSnapshot,
)
from echomind.domain.ports import (
    IBondDepthStore,
    ILlmGateway,
    IMemoryReader,
    IMemoryWriter,
    IPersonaConstraintStore,
    ITurnTraceStore,
    IWorkingStateStore,
)
from echomind.mind.ban_control import extract_new_bans
from echomind.mind.bond_scoring import attach_bond_depth as attach
from echomind.mind.chord_cache import remember_chord
from echomind.mind.chord_gateway import apply_probe_if_allowed, chord_for, format_recent
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
    build_turn_record,
    consolidate_turn_memory,
    run_hippocampal_batch_consolidation,
)
from echomind.mind.perceptual_gate import PerceptualGate
from echomind.mind.personality import synthesize_live_persona_directive
from echomind.mind.plasticity import NeuroplasticityEngine, apply_chord_reward
from echomind.mind.salience_hydraulics import apply_speaking_satiation
from echomind.mind.shadow_appraisal import (
    ShadowAppraisalResult,
    evaluate_shadow_appraisal,
    filter_unfulfilled_intentions,
)
from echomind.mind.subconscious_probe import (
    SubconsciousChordProbe,
    SubconsciousChordResult,
)


class CognitiveCoreFacade:
    """Unified 12-Layer Cognitive Core Facade satisfying ICognitiveCoreFacade."""

    def __init__(
        self, mem_reader: IMemoryReader, mem_writer: IMemoryWriter,
        working_store: IWorkingStateStore, owner_qq: str = "",
        default_group_key: str = "group:10002002", *,
        constraint_store: IPersonaConstraintStore | None = None,
        trace_store: ITurnTraceStore | None = None,
        bond_store: IBondDepthStore | None = None,
        operator_ids: tuple[str, ...] = (),
    ) -> None:
        self._reader, self._writer, self._working = mem_reader, mem_writer, working_store
        self._owner_qq, self._default_group = owner_qq, default_group_key
        self._gate, self._calibrator = PerceptualGate(), EpistemicCalibrator()
        self._constraints, self._traces = constraint_store, trace_store
        self._bond_store = bond_store
        self._operator_ids = tuple(operator_ids) or ((owner_qq,) if owner_qq else ())
        self._plasticity = NeuroplasticityEngine(working_store)
        self._last_active_ms: int = int(time.time() * 1000)
        self._gate_log: list[dict[str, Any]] = []
        self._sub_probe: SubconsciousChordProbe | None = None
        self._chord_cache: dict[str, SubconsciousChordResult] = {}

    def set_subconscious_probe(self, probe: SubconsciousChordProbe | None) -> None:
        self._sub_probe = probe

    def cache_chord(self, message_id: str, chord: SubconsciousChordResult) -> None:
        remember_chord(self._chord_cache, message_id, chord)

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
        s_bond = await self._reader.get_social_bond(percept.chat_key, percept.sender_id)
        vocab = frozenset(f.subject.lower() for f in facts)
        dec = self._gate.evaluate(
            percept, snap, vocab, rivals, talkativeness=talk,
            record_state=not dry_run, params=params, speaker_bond=s_bond,
        )
        if not dry_run and self._sub_probe is not None:
            snap, dec = await apply_probe_if_allowed(
                self._sub_probe, percept, snap, dec, s_bond,
                working=self._working, cache=self._chord_cache,
                recent_lines=format_recent(self._gate_log, percept.chat_key),
                in_ambient_cooldown=self._gate.ambient_cooldown_active(
                    percept.chat_key, percept.timestamp_ms
                ),
            )
            if dec.should_wake and dec.tier > 1:
                self._gate.mark_ambient_wake(percept.chat_key, percept.timestamp_ms)
        if not dry_run:
            self._gate_log = record_gate_decision(self._gate_log, percept, dec)
        return dec

    async def _recall_and_reinforce(
        self, chat_key: str, triggers: tuple[Percept, ...], uids: tuple[str, ...],
        now_ms: int, dry_run: bool = False,
    ) -> tuple[RecalledMemoryItem, ...]:
        cards = await self._reader.get_episodic_cards(chat_key)
        recalled = recall_episodic_memories(
            cards, " ".join(p.text for p in triggers), uids, now_ms, top_k=8
        )
        if not dry_run:
            for r_item in recalled:
                await self._writer.reinforce_episodic_card(r_item.card.card_id, now_ms)
        return recalled

    async def _apply_shadow_and_save(
        self, chat_key: str, base_snap: WorkingSnapshot, triggers: tuple[Percept, ...],
        bonds_map: dict[str, SocialBondProfile], *, dry_run: bool = False,
        chord: SubconsciousChordResult | None = None,
    ) -> tuple[WorkingSnapshot, ShadowAppraisalResult, str]:
        params = await self._working.get_plastic_params()
        traits = await self._working.sync_persona_traits()
        shadow = evaluate_shadow_appraisal(
            triggers, base_snap.affect, params, traits, bonds_map, chord=chord,
        )
        raw_irr = base_snap.affect.irritation + shadow.irritation_delta
        new_irr = max(0.0, min(100.0, round(raw_irr, 2)))
        updated = base_snap.model_copy(
            update={"affect": base_snap.affect.model_copy(update={"irritation": new_irr})}
        )
        if not dry_run:
            await self._working.save_working_state(updated)
            if new_irr > 85.0 and triggers and triggers[-1].sender_id != self._owner_qq:
                last = triggers[-1]
                self._gate.impose_cold_shoulder(chat_key, last.sender_id, last.timestamp_ms)
        return updated, shadow, synthesize_live_persona_directive(params, traits)

    async def _advance(
        self, chat_key: str, triggers: tuple[Percept, ...], facts: tuple[SemanticFact, ...],
        bonds_map: dict[str, SocialBondProfile] | None = None,
        chord: SubconsciousChordResult | None = None,
    ) -> tuple[WorkingSnapshot, AttentionDecision | None, float]:
        snap = await self._working.load_working_state("global")
        params = await self._working.get_plastic_params()
        skep = params["skepticism"].value if "skepticism" in params else 55.0
        talk = params["talkativeness"].value if "talkativeness" in params else 58.0
        cur_rate = params["curiosity_rate"].value if "curiosity_rate" in params else 65.0
        rivals = await self._reader.get_rival_names(chat_key)
        vocab = frozenset(f.subject.lower() for f in facts)
        s_bond = bonds_map.get(triggers[-1].sender_id) if (bonds_map and triggers) else None
        last_dec = (
            self._gate.evaluate(
                triggers[-1], snap, vocab, rivals, talkativeness=talk,
                record_state=False, params=params, speaker_bond=s_bond,
            ) if triggers else None
        )
        unknowns = last_dec.detected_unknown_terms if last_dec else ()
        updated = apply_turn_affect_and_drives(
            snap, triggers, rivals, unknowns,
            curiosity_rate=cur_rate, bonds_map=bonds_map, params=params, chord=chord,
        )
        return updated, last_dec, skep

    async def _resolve_bans(self, tr: tuple[Percept, ...], dry: bool = False) -> tuple[str, ...]:
        if self._constraints is None:
            return ()
        new_bans = extract_new_bans(tr, self._operator_ids)
        if not dry:
            for phrase in new_bans:
                await self._constraints.add_banned_phrase(phrase, "主人明令禁止的口癖")
        existing = await self._constraints.get_banned_phrases()
        return tuple(dict.fromkeys([*new_bans, *existing]))

    async def build_cognitive_frame(
        self, chat_key: str, triggers: tuple[Percept, ...], *, dry_run: bool = False
    ) -> CognitiveFrame:
        now_ms, tr = int(time.time() * 1000), triggers
        scene: Literal["group", "private"] = "private" if "private:" in chat_key else "group"
        facts = await self._reader.get_semantic_facts(chat_key)
        uids = extract_mentioned_uids(tr, facts)
        pairs = [(u, await self._reader.get_social_bond(chat_key, u)) for u in uids]
        bm = await attach(self._bond_store, {u: b for u, b in pairs if b is not None})
        chord = await chord_for(self._sub_probe, tr, bm, self._chord_cache, dry_run)
        base_snap, last_dec, skep = await self._advance(chat_key, tr, facts, bm, chord)
        bans = await self._resolve_bans(tr, dry_run)
        snap, shadow, p_blk = await self._apply_shadow_and_save(
            chat_key, base_snap, tr, bm, dry_run=dry_run, chord=chord
        )
        warns, _ = self._calibrator.calibrate(tr, facts, bm, skepticism=skep)
        rules = await self._reader.get_procedural_rules(chat_key)
        recalled = await self._recall_and_reinforce(chat_key, tr, uids, now_ms, dry_run)
        cur_p = build_curiosity_prompts(tr, last_dec, snap.affect)
        unk = last_dec.detected_unknown_terms if last_dec else ()
        cyber = compute_cybernetic_core(
            scene, snap, tr, bm,
            unknown_terms=unk, warnings=warns, chord_reagents=chord.reagents if chord else (),
        )
        rel_facts = select_relevant_facts(facts, " ".join(p.text for p in tr), limit=28)
        core_blk = render_mind_block(
            scene, snap, bonds=bm, facts=rel_facts, warnings=warns,
            shadow_directives=shadow.shadow_directives, rule_lines=match_active_rules(rules, tr),
            recalled=recalled, cur_prompts=cur_p, bans=bans,
        )
        return CognitiveFrame(
            chat_key=chat_key, scene=scene, must_reply=bool(last_dec and last_dec.tier == 1),
            affect=snap.affect, drives=snap.drives,
            rendered_mind_block=f"{core_blk}\n{render_cybernetic_core_directive(cyber)}\n{p_blk}",
            epistemic_warnings=(*warns, *shadow.shadow_directives),
            curiosity_prompts=cur_p, banned_phrases=bans, cybernetic_core=cyber,
        )

    async def on_turn_completed(self, outcome: TurnOutcome) -> None:
        now_ms, o = int(time.time() * 1000), outcome
        if o.sent_texts:
            self._gate.mark_bot_spoke(o.chat_key, o.sent_texts, now_ms, o.triggers)
            snap = await self._working.load_working_state("global")
            rem = filter_unfulfilled_intentions(snap.intentions, o.sent_texts, now_ms)
            satiated = apply_speaking_satiation(
                snap.model_copy(update={"intentions": rem}), o.sent_texts, o.tools_used
            )
            await self._working.save_working_state(satiated)
        if self._traces is not None and o.steps:
            await self._traces.save_turn(build_turn_record(o, now_ms))
        o, chord = apply_chord_reward(o, self._chord_cache)
        await consolidate_turn_memory(
            self._reader, self._writer, o, now_ms, self._owner_qq, chord=chord
        )
        await self._plasticity.adapt_from_outcome(o)

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
            self._last_active_ms = max(self._last_active_ms, now_ms)
            await self._working.save_working_state(consume_proposal_snapshot(raw_snap, proposal))
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
