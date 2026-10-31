"""Per-turn SocialBond/Fact updates and Hippocampal Batch Memory Summarization (Zero Lexicons)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from echomind.domain.models import (
    EpisodicCard,
    Percept,
    PersonaTrait,
    SemanticFact,
    SocialBondProfile,
    TurnOutcome,
    TurnRecord,
)
from echomind.domain.ports import ILlmGateway, IMemoryReader, IMemoryWriter, IWorkingStateStore
from echomind.mind.cybernetics import crystallize_self_organizing_schemas
from echomind.mind.hippocampus import (
    HippocampalBondAdjustment,
    build_hippocampus_messages,
    parse_consolidation_json,
)
from echomind.mind.memory_budget import consolidation_budget, consolidation_thinking
from echomind.mind.relation_persist import persist_relations
from echomind.mind.working_update import mutate_working_state

if TYPE_CHECKING:
    from echomind.mind.subconscious_probe import SubconsciousChordResult

# param: data:affinity-quantiles - q25/50/75/90 of active bonds; CI in the ledger.
AFFINITY_THRESHOLDS = (31.77, 40.75, 48.2, 56.79)
DUNBAR_ACQUAINTANCE_CAP = 85.0
RIVAL_EQUILIBRIUM = 45.0

def build_turn_record(outcome: TurnOutcome, now_ms: int) -> TurnRecord:
    """Construct an immutable TurnRecord from a completed TurnOutcome."""
    last = outcome.triggers[-1] if outcome.triggers else None
    trig_label = f"{last.sender_name}：{last.text[:40]}" if last else ""
    models = [s.name for s in outcome.steps if s.kind == "llm" and s.name]
    return TurnRecord(
        turn_id=outcome.session_id, chat_key=outcome.chat_key, ts=now_ms,
        trigger=trig_label, status=outcome.status, rounds=len(models),
        sent_count=len(outcome.sent_texts), total_ms=outcome.total_ms,
        model=models[-1] if models else "", context_count=outcome.context_count,
        trigger_count=len(outcome.triggers), system_prompt=outcome.system_prompt,
        user_prompt=outcome.user_prompt, steps=outcome.steps,
    )


def compute_affinity_level(score: float) -> int:
    """Map raw affinity score to Lv.1..Lv.5 using the fitted quantile thresholds."""
    return 1 + sum(1 for threshold in AFFINITY_THRESHOLDS if score >= threshold)


def cubic_trust_affinity_cap(trust_score: float, *, is_rival: bool = False) -> float:
    """Law 3: Cubic trust-bounded affinity ceiling A_max(trust) = 35 + 465 * trust^3."""
    if is_rival:
        return 60.0
    t_clamped = max(0.1, min(1.0, trust_score))
    return round(35.0 + 465.0 * (t_clamped**3), 2)


def _default_bond(chat_key: str, percept: Percept, is_owner: bool) -> SocialBondProfile:
    score = 30.0
    return SocialBondProfile(
        chat_key=chat_key, user_id=percept.sender_id,
        user_name=percept.sender_name or percept.sender_id,
        group_role="admin" if is_owner else "member",
        affinity_score=score, affinity_level=compute_affinity_level(score),
        msg_count=0, trust_score=0.75,
    )


def _negative_affinity_override(
    reward: float, *, conflict: bool, spoof_called_out: bool, bot_pushback: bool
) -> float | None:
    if conflict:
        return -6.0
    if spoof_called_out:
        return -3.5
    if bot_pushback:
        return -3.0
    if reward < 0.0:
        return round(reward * 4.5, 2)
    return None


def compute_affinity_delta(
    percept: Percept, base_score: float, reward: float, *,
    conflict: bool = False, spoof_called_out: bool = False,
    is_rival: bool = False, bot_pushback: bool = False,
) -> float:
    """Three-Attractor Ornstein-Uhlenbeck relational delta (Asymmetric Negativity + Dunbar Cap)."""
    neg_val = _negative_affinity_override(
        reward, conflict=conflict, spoof_called_out=spoof_called_out, bot_pushback=bot_pushback
    )
    if neg_val is not None:
        return neg_val
    if is_rival:
        return round((RIVAL_EQUILIBRIUM - base_score) * 0.18, 2)
    direct = any(
        (percept.is_at_me, percept.is_called_by_name, percept.is_quoted_me, percept.is_poke_me)
    )
    if reward >= 0.35:
        raw_gain = 1.5 + (reward - 0.30) * 4.5 + (0.9 if direct else 0.0)
        damping = 1.0 / (1.0 + max(0.0, base_score) / 180.0)
        return round(max(0.15, raw_gain * damping), 2)
    if base_score < DUNBAR_ACQUAINTANCE_CAP:
        step = 1.10 if direct else 0.55
        ratio = (DUNBAR_ACQUAINTANCE_CAP - base_score) / DUNBAR_ACQUAINTANCE_CAP
        return round(max(0.08, step * ratio), 2)
    return round(-0.12 * ((base_score - DUNBAR_ACQUAINTANCE_CAP) / DUNBAR_ACQUAINTANCE_CAP), 2)


def compute_trust_delta(
    base_trust: float, reward: float, *,
    conflict: bool = False, spoof_called_out: bool = False,
) -> float:
    """Compute bidirectional epistemic trust delta (flattery capped above 0.82)."""
    if conflict:
        return -0.08
    if spoof_called_out:
        return -0.04
    if reward <= -0.4:
        return -0.03
    if reward >= 0.4:
        return 0.02 if base_trust < 0.82 else 0.003
    return 0.005 if base_trust < 0.80 else 0.0


async def update_sender_bond(
    reader: IMemoryReader, writer: IMemoryWriter, chat_key: str,
    percept: Percept, reward: float = 0.0, *, operator_ids: tuple[str, ...] = (),
    conflict: bool = False, spoof_called_out: bool = False, bot_pushback: bool = False,
) -> None:
    """Update a member's affinity score (Three-Attractor + Trust Cap) and trust score."""
    is_owner = percept.sender_id in operator_ids
    base = await reader.get_social_bond(chat_key, percept.sender_id) or _default_bond(
        chat_key, percept, is_owner
    )
    t_delta = compute_trust_delta(
        base.trust_score, reward, conflict=conflict, spoof_called_out=spoof_called_out
    )
    new_trust = 1.0 if is_owner else round(max(0.1, min(0.98, base.trust_score + t_delta)), 3)
    delta = compute_affinity_delta(
        percept, base.affinity_score, reward,
        conflict=conflict, spoof_called_out=spoof_called_out,
        is_rival=base.is_rival, bot_pushback=bot_pushback,
    )
    eff_delta = 0.0 if (new_trust < 0.55 and delta > 0) else delta
    t_cap = cubic_trust_affinity_cap(new_trust, is_rival=base.is_rival)
    raw_aff = max(0.0, min(t_cap, base.affinity_score + eff_delta))
    new_score = round(raw_aff, 2)
    await writer.upsert_social_bond(
        base.model_copy(
            update={
                "user_name": percept.sender_name or base.user_name,
                "affinity_score": new_score,
                "affinity_level": compute_affinity_level(new_score),
                "last_seen_ms": percept.timestamp_ms,
                "trust_score": new_trust,
            }
        )
    )


async def _extract_explicit_fact(
    writer: IMemoryWriter, outcome: TurnOutcome, last: Percept,
    operator_ids: tuple[str, ...] = (), chord: SubconsciousChordResult | None = None,
) -> None:
    clause = chord.explicit_fact.strip() if chord is not None else ""
    if outcome.epistemic_conflict_detected or not clause:
        return
    is_owner = last.sender_id in operator_ids
    await writer.upsert_semantic_fact(
        SemanticFact(
            chat_key=outcome.chat_key, subject=f"{last.sender_name}({last.sender_id})"[:40],
            fact_text=f"{last.sender_name}提到：{clause}"[:160],
            confidence=0.88 if is_owner else 0.58, is_locked=False,
            source="owner" if is_owner else "peer",
        )
    )


async def consolidate_turn_memory(
    reader: IMemoryReader, writer: IMemoryWriter, outcome: TurnOutcome,
    _now_ms: int, operator_ids: tuple[str, ...] = (), *,
    chord: SubconsciousChordResult | None = None,
) -> None:
    """Update social bond affinity/trust and explicit facts on turn completion."""
    if not outcome.triggers:
        return
    called_out = bool(chord and chord.spoof_attempt)
    pushed_back = bool((chord and chord.annoyance >= 2) or outcome.social_reward <= -0.40)
    seen: set[str] = set()
    for p in reversed(outcome.triggers):
        if p.sender_id in seen:
            continue
        seen.add(p.sender_id)
        await update_sender_bond(
            reader, writer, outcome.chat_key, p, outcome.social_reward,
            operator_ids=operator_ids, conflict=outcome.epistemic_conflict_detected,
            spoof_called_out=called_out, bot_pushback=pushed_back,
        )
    if outcome.sent_texts:
        await _extract_explicit_fact(
            writer, outcome, outcome.triggers[-1], operator_ids, chord=chord
        )


def _extract_llm_text(resp: dict[str, Any]) -> str:
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    raw_msg = first.get("message")
    msg = raw_msg if isinstance(raw_msg, dict) else {}
    return str(msg.get("content") or "").strip()


async def _apply_hippocampal_working_updates(
    working_store: IWorkingStateStore | None, new_trait: str, new_activity: str
) -> None:
    if working_store is None:
        return
    if new_trait:
        trait = PersonaTrait(category="habit", trait_text=new_trait, strength=6)
        await working_store.sync_persona_traits(new_trait=trait)
    if new_activity:
        await mutate_working_state(
            working_store, "global",
            lambda s: s.model_copy(update={"current_activity": new_activity}),
        )


async def _penalize_card_spoofers(
    chat_key: str, card: EpisodicCard, reader: IMemoryReader, writer: IMemoryWriter
) -> None:
    if card.importance < 4.5 and not card.key_detail:
        return
    for uid in card.participants:
        bond = await reader.get_social_bond(chat_key, uid)
        if bond and bond.group_role != "owner" and bond.affinity_score < 9000.0:
            new_t = round(max(0.1, bond.trust_score - 0.05), 3)
            await writer.upsert_social_bond(bond.model_copy(update={"trust_score": new_t}))


async def _apply_hippocampal_bond_adjustments(
    chat_key: str, adjs: tuple[HippocampalBondAdjustment, ...],
    reader: IMemoryReader, writer: IMemoryWriter,
) -> None:
    for adj in adjs:
        bond = await reader.get_social_bond(chat_key, adj.user_id)
        if not bond or bond.group_role == "owner" or bond.affinity_score >= 9000.0:
            continue
        new_t = round(max(0.1, min(0.98, bond.trust_score + adj.trust_delta)), 3)
        t_cap = cubic_trust_affinity_cap(new_t, is_rival=bond.is_rival)
        new_a = round(max(0.0, min(t_cap, bond.affinity_score + adj.affinity_delta)), 2)
        lvl = compute_affinity_level(new_a)
        upd = {"affinity_score": new_a, "affinity_level": lvl, "trust_score": new_t}
        await writer.upsert_social_bond(bond.model_copy(update=upd))


async def _crystallize_schemas(
    chat_key: str, reader: IMemoryReader, writer: IMemoryWriter
) -> None:
    cards = await reader.get_episodic_cards(chat_key)
    facts = await reader.get_semantic_facts(chat_key)
    for schema_fact in crystallize_self_organizing_schemas(chat_key, cards, facts):
        await writer.upsert_semantic_fact(schema_fact)


async def run_hippocampal_batch_consolidation(
    chat_key: str, reader: IMemoryReader, writer: IMemoryWriter,
    llm: ILlmGateway, transcript_lines: tuple[str, ...], *,
    now_ms: int = 0, working_store: IWorkingStateStore | None = None, role_text: str = "",
) -> int:
    """Summarize a batch of dialogue lines into Hippocampal cards and grown persona traits."""
    if len(transcript_lines) < 4:
        return 0
    facts = await reader.get_semantic_facts(chat_key)
    locked = tuple(f for f in facts if f.is_locked)
    msgs = build_hippocampus_messages(chat_key, transcript_lines, locked, role_text=role_text)
    resp = await llm.complete(msgs, temperature=0.3, max_tokens=consolidation_budget(),
                              chat_key=chat_key, thinking_off=not consolidation_thinking())
    batch = parse_consolidation_json(chat_key, _extract_llm_text(resp), now_ms)
    for card in batch.cards:
        await writer.save_episodic_card(card)
        await _penalize_card_spoofers(chat_key, card, reader, writer)
    for fact in batch.facts:
        await writer.upsert_semantic_fact(fact)
    await persist_relations(writer, batch.relations)
    for rule in batch.rules:
        await writer.upsert_procedural_rule(rule)
    await _apply_hippocampal_bond_adjustments(chat_key, batch.bond_adjustments, reader, writer)
    await _crystallize_schemas(chat_key, reader, writer)
    await _apply_hippocampal_working_updates(
        working_store, batch.new_persona_trait, batch.new_activity
    )
    return len(batch.cards)
