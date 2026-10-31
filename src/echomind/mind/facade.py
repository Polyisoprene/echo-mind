"""M3.4/M3.5 CognitiveCoreFacade: Single entry point exposed to Runtime (Law of Demeter)."""

from __future__ import annotations

import time
from typing import Any, Literal

from echomind.domain.models import (
    AttentionDecision,
    CognitiveFrame,
    Percept,
    ProactiveProposal,
    SemanticFact,
    SocialBondProfile,
    TurnOutcome,
    WorkingSnapshot,
)
from echomind.domain.ports import (
    IBondDepthStore,
    IDisclosureLog,
    ILlmGateway,
    IMemoryReader,
    IMemoryWriter,
    IPersonaConstraintStore,
    IPersonaLayerStore,
    ITurnTraceStore,
    IWorkingStateStore,
)
from echomind.mind.ban_control import resolve_bans
from echomind.mind.bond_scoring import attach_bond_depth as attach
from echomind.mind.bot_belief import rebuild as rebuild_beliefs, set_beliefs
from echomind.mind.chord_cache import remember_chord
from echomind.mind.chord_gateway import apply_probe_if_allowed, chord_for
from echomind.mind.circadian import record_gate_decision
from echomind.mind.cybernetics import (
    compute_cybernetic_core,
    render_cybernetic_core_directive,
)
from echomind.mind.dialogue_context import DialogueContext
from echomind.mind.drives import apply_turn_affect_and_drives
from echomind.mind.ebbinghaus import select_relevant_facts
from echomind.mind.epistemic import EpistemicCalibrator
from echomind.mind.facade_autonomy import run_autonomous_tick
from echomind.mind.facade_memory import (
    audience_of,
    consolidate_dialogue,
    gate_frame,
    load_facts,
    recall_and_reinforce,
)
from echomind.mind.frame_renderer import (
    build_curiosity_prompts,
    match_active_rules,
    render_mind_block,
)
from echomind.mind.memory_consolidator import build_turn_record, consolidate_turn_memory
from echomind.mind.perceptual_gate import PerceptualGate
from echomind.mind.person_level_service import PersonLevelService
from echomind.mind.persona_dynamics import param_value
from echomind.mind.persona_stance import apply_stance_for
from echomind.mind.persona_state import effective_params_of
from echomind.mind.personality import synthesize_live_persona_directive
from echomind.mind.plasticity import NeuroplasticityEngine, apply_chord_reward
from echomind.mind.recall_types import RecalledMemoryItem
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
        working_store: IWorkingStateStore,
        default_group_key: str = "group:10002002", *,
        constraint_store: IPersonaConstraintStore | None = None,
        trace_store: ITurnTraceStore | None = None,
        bond_store: IBondDepthStore | None = None,
        operator_ids: tuple[str, ...] = (),
        persona_layers: IPersonaLayerStore | None = None,
        person_level: PersonLevelService | None = None,
        disclosure_log: IDisclosureLog | None = None,
    ) -> None:
        self._reader, self._writer, self._working = mem_reader, mem_writer, working_store
        self._default_group = default_group_key
        self._gate, self._calibrator = PerceptualGate(), EpistemicCalibrator()
        self._constraints, self._traces = constraint_store, trace_store
        self._bond_store = bond_store
        self._operator_ids = tuple(operator_ids)
        self._layers = persona_layers
        self._person_level = person_level
        self._disclosure_log = disclosure_log
        self._plasticity = NeuroplasticityEngine(working_store, persona_layers)
        self._last_active_ms: int = int(time.time() * 1000)
        self._gate_log: list[dict[str, Any]] = []
        self._sub_probe: SubconsciousChordProbe | None = None
        self._chord_cache: dict[str, SubconsciousChordResult] = {}
        self._dialogue = DialogueContext()

    def set_subconscious_probe(self, probe: SubconsciousChordProbe | None) -> None:
        self._sub_probe = probe

    def cache_chord(self, message_id: str, chord: SubconsciousChordResult) -> None:
        remember_chord(self._chord_cache, message_id, chord)


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
        params = await effective_params_of(self._working, self._layers, percept.timestamp_ms)
        talk = params["talkativeness"].value if "talkativeness" in params else 58.0
        facts = await self._reader.get_semantic_facts(percept.chat_key)
        set_beliefs(rebuild_beliefs(tuple((f.subject, f.fact_text, f.confidence) for f in facts)))
        rivals = await self._reader.get_rival_names(percept.chat_key)
        s_bond = await self._reader.get_social_bond(percept.chat_key, percept.sender_id)
        vocab = frozenset(f.subject.lower() for f in facts)
        dec = self._gate.evaluate(percept, snap, vocab, rivals, talkativeness=talk,
                                  record_state=not dry_run, params=params, speaker_bond=s_bond)
        recent = self._dialogue.note(percept.sender_name, percept.text)
        if not dry_run and self._sub_probe is not None:
            snap, dec = await apply_probe_if_allowed(
                self._sub_probe, percept, snap, dec, s_bond, working=self._working,
                cache=self._chord_cache, recent_lines=recent,
                in_ambient_cooldown=self._gate.ambient_cooldown_active(
                    percept.chat_key, percept.timestamp_ms))
            if dec.should_wake and dec.tier > 1:
                self._gate.mark_ambient_wake(percept.chat_key, percept.timestamp_ms)
        if not dry_run:
            self._gate_log = record_gate_decision(self._gate_log, percept, dec)
        return dec

    async def _recall_and_reinforce(
        self, chat_key: str, triggers: tuple[Percept, ...], uids: tuple[str, ...],
        now_ms: int, dry_run: bool = False,
    ) -> tuple[RecalledMemoryItem, ...]:
        return await recall_and_reinforce(
            self._reader, self._writer, chat_key=chat_key, triggers=triggers,
            uids=uids, now_ms=now_ms, dry_run=dry_run,
        )

    async def _apply_shadow_and_save(
        self, chat_key: str, base_snap: WorkingSnapshot, triggers: tuple[Percept, ...],
        bonds_map: dict[str, SocialBondProfile], *, dry_run: bool = False,
        chord: SubconsciousChordResult | None = None,
    ) -> tuple[WorkingSnapshot, ShadowAppraisalResult, str]:
        now_ms = int(time.time() * 1000)
        params = await effective_params_of(self._working, self._layers, now_ms)
        profiles = await self._person_level.profiles(now_ms) if self._person_level else {}
        params = apply_stance_for(
            params, bonds_map, triggers[-1].sender_id if triggers else "", profiles
        )
        traits = await self._working.sync_persona_traits()
        shadow = evaluate_shadow_appraisal(
            triggers, base_snap.affect, params, traits, bonds_map,
            chord=chord, profiles=profiles,
        )
        raw_irr = base_snap.affect.irritation + shadow.irritation_delta
        new_irr = max(0.0, min(100.0, round(raw_irr, 2)))
        affect = base_snap.affect.model_copy(update={"irritation": new_irr})
        updated = base_snap.model_copy(update={"affect": affect})
        if not dry_run:
            await self._working.save_working_state(updated)
            if new_irr > 85.0 and triggers:
                last = triggers[-1]
                self._gate.impose_cold_shoulder(chat_key, last.sender_id, last.timestamp_ms)
        return updated, shadow, synthesize_live_persona_directive(params, traits)

    async def _advance(
        self, chat_key: str, triggers: tuple[Percept, ...], facts: tuple[SemanticFact, ...],
        bonds_map: dict[str, SocialBondProfile] | None = None,
        chord: SubconsciousChordResult | None = None,
    ) -> tuple[WorkingSnapshot, AttentionDecision | None, float]:
        snap = await self._working.load_working_state("global")
        now_ms = int(time.time() * 1000)
        params = await effective_params_of(self._working, self._layers, now_ms)
        profiles = await self._person_level.profiles(now_ms) if self._person_level else {}
        params = apply_stance_for(
            params, bonds_map, triggers[-1].sender_id if triggers else "", profiles
        )
        skep = param_value(params, "skepticism", 55.0)
        talk = param_value(params, "talkativeness", 58.0)
        cur_rate = param_value(params, "curiosity_rate", 65.0)
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
            snap, triggers, rivals, unknowns, curiosity_rate=cur_rate,
            bonds_map=bonds_map, params=params, chord=chord, profiles=profiles,
        )
        return updated, last_dec, skep

    async def build_cognitive_frame(
        self, chat_key: str, triggers: tuple[Percept, ...], *, dry_run: bool = False
    ) -> CognitiveFrame:
        now_ms, tr = int(time.time() * 1000), triggers
        scene: Literal["group", "private"] = "private" if "private:" in chat_key else "group"
        facts, uids = await load_facts(self._reader, chat_key, tr)
        set_beliefs(rebuild_beliefs(tuple((f.subject, f.fact_text, f.confidence) for f in facts)))
        pairs = [(u, await self._reader.get_social_bond(chat_key, u)) for u in uids]
        bm = await attach(self._bond_store, {u: b for u, b in pairs if b is not None})
        chord = await chord_for(self._sub_probe, tr, bm, self._chord_cache, dry_run)
        base_snap, last_dec, skep = await self._advance(chat_key, tr, facts, bm, chord)
        bans = await resolve_bans(self._constraints, tr, self._operator_ids, dry=dry_run)
        snap, shadow, p_blk = await self._apply_shadow_and_save(
            chat_key, base_snap, tr, bm, dry_run=dry_run, chord=chord
        )
        warns, _ = self._calibrator.calibrate(tr, facts, bm, skepticism=skep)
        rules = await self._reader.get_procedural_rules(chat_key)
        recalled = await self._recall_and_reinforce(chat_key, tr, uids, now_ms, dry_run)
        facts, recalled = await gate_frame(
            facts, recalled, audience_of(uids, tr), chat_key, self._disclosure_log
        )
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
        for sent in outcome.sent_texts:
            self._dialogue.add("我", sent)
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
            self._reader, self._writer, o, now_ms, chord=chord
        )
        await self._plasticity.adapt_from_outcome(o)

    async def run_autonomous_tick(self, now_ms: int) -> ProactiveProposal | None:
        proposal, self._last_active_ms = await run_autonomous_tick(
            self._working, self._plasticity, self._last_active_ms,
            self._operator_ids, self._default_group, now_ms=now_ms,
        )
        return proposal

    async def consolidate_dialogue_batch(
        self, chat_key: str, transcript_lines: tuple[str, ...],
        llm: ILlmGateway, *, role_text: str = "",
    ) -> int:
        return await consolidate_dialogue(
            self._reader, self._writer, llm, self._working,
            chat_key=chat_key, transcript_lines=transcript_lines, role_text=role_text,
        )
