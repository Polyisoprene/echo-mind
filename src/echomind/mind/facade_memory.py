"""Memory recall, dialogue consolidation and the frame-level disclosure gate."""

from __future__ import annotations

import time

from echomind.domain.models import Percept, SemanticFact, SocialBondProfile
from echomind.domain.ports import (
    IBondDepthStore,
    IDisclosureLog,
    ILlmGateway,
    IMemoryReader,
    IMemoryWriter,
    IWorkingStateStore,
)
from echomind.mind.bond_scoring import attach_bond_depth as attach
from echomind.mind.bot_belief import rebuild as rebuild_beliefs, set_beliefs
from echomind.mind.disclosure import gate_episode, gate_fact
from echomind.mind.disclosure_choice import DisclosureChoice, choose
from echomind.mind.ebbinghaus import (
    extract_mentioned_uids,
    recall_episodic_memories,
)
from echomind.mind.memory_consolidator import run_hippocampal_batch_consolidation
from echomind.mind.ranker_fusion import unified_rank
from echomind.mind.recall_types import RecalledMemoryItem
from echomind.mind.semantic_memory import SemanticMemoryRetriever


async def recall_and_reinforce(
    reader: IMemoryReader,
    writer: IMemoryWriter,
    *,
    chat_key: str,
    triggers: tuple[Percept, ...],
    uids: tuple[str, ...],
    now_ms: int,
    dry_run: bool = False,
) -> tuple[RecalledMemoryItem, ...]:
    cards = await reader.get_episodic_cards(chat_key)
    recalled = recall_episodic_memories(cards, " ".join(p.text for p in triggers), uids, now_ms)
    if not dry_run:
        for item in recalled:
            await writer.reinforce_episodic_card(item.card.card_id, now_ms)
    return recalled


async def consolidate_dialogue(
    reader: IMemoryReader,
    writer: IMemoryWriter,
    llm: ILlmGateway,
    working: IWorkingStateStore,
    *,
    chat_key: str,
    transcript_lines: tuple[str, ...],
    role_text: str = "",
) -> int:
    return await run_hippocampal_batch_consolidation(
        chat_key, reader, writer, llm, transcript_lines,
        now_ms=int(time.time() * 1000), working_store=working, role_text=role_text,
    )


async def load_facts(
    reader: IMemoryReader, chat_key: str, triggers: tuple[Percept, ...]
) -> tuple[tuple[SemanticFact, ...], tuple[str, ...]]:
    facts = await reader.get_semantic_facts(chat_key)
    set_beliefs(chat_key, rebuild_beliefs(
        tuple((f.subject, f.fact_text, f.confidence) for f in facts)))
    uids = extract_mentioned_uids(triggers, facts)
    facts = await reader.get_semantic_facts(chat_key, person_ids=uids)
    return facts, uids


def audience_of(uids: tuple[str, ...], triggers: tuple[Percept, ...]) -> frozenset[str]:
    sender = triggers[-1].sender_id if triggers else ""
    return frozenset((*uids, sender)) - {""}


def _persona_choice(
    fact: SemanticFact, traits: dict[str, float], rival_present: bool, granted: bool
) -> DisclosureChoice | None:
    if fact.scope != "person":
        return None
    return choose(
        sensitivity=fact.sensitivity, has_owner=bool(fact.owner_id),
        rival_present=rival_present, traits=traits, granted=granted,
    )


async def _log_disclosure(
    log: IDisclosureLog | None, *, kind: str, memory_id: int, venue: str,
    audience: frozenset[str], action: str, reason: str,
) -> None:
    if log is None:
        return
    await log.log_disclosure(
        memory_kind=kind, memory_id=memory_id, venue=venue,
        audience=tuple(sorted(audience)), action=action, reason=reason,
    )


async def _granted(
    fact: SemanticFact, audience: frozenset[str], log: IDisclosureLog | None
) -> bool:
    if fact.sensitivity != "secret" or log is None:
        return False
    for person in audience:
        if await log.has_grant(
            memory_kind="semantic", memory_id=fact.fact_id, grantee_id=person
        ):
            return True
    return False


async def _traits_and_rival(
    working: IWorkingStateStore | None,
    bonds: dict[str, SocialBondProfile] | None,
    audience: frozenset[str],
) -> tuple[dict[str, float], bool]:
    if working is None:
        return {}, False
    traits = {key: spec.value for key, spec in (await working.get_plastic_params()).items()}
    rival = any(b.is_rival and b.user_id in audience for b in (bonds or {}).values())
    return traits, rival


async def _handle_choice(
    choice: DisclosureChoice | None,
    fact: SemanticFact,
    log: IDisclosureLog | None,
    audience: frozenset[str],
    venue: str,
) -> bool:
    """Return True when the persona keeps the fact (so the caller skips it)."""
    if choice is None:
        return False
    if choice.action == "keep":
        await _log_disclosure(log, kind="semantic", memory_id=fact.fact_id, venue=venue,
                              audience=audience, action="keep", reason=choice.reason)
        return True
    await _log_disclosure(log, kind="semantic", memory_id=fact.fact_id, venue=venue,
                          audience=audience, action=choice.action, reason="persona")
    return False


async def _gate_facts(
    facts: tuple[SemanticFact, ...],
    audience: frozenset[str],
    venue: str,
    log: IDisclosureLog | None,
    *,
    working: IWorkingStateStore | None = None,
    bonds: dict[str, SocialBondProfile] | None = None,
) -> tuple[SemanticFact, ...]:
    traits, rival = await _traits_and_rival(working, bonds, audience)
    kept: list[SemanticFact] = []
    for fact in facts:
        granted = await _granted(fact, audience, log)
        decision = gate_fact(fact, audience, venue, granted=granted)
        if not decision.allowed:
            await _log_disclosure(log, kind="semantic", memory_id=fact.fact_id, venue=venue,
                                  audience=audience, action="keep", reason=decision.reason)
            continue
        choice = _persona_choice(fact, traits, rival, granted)
        if await _handle_choice(choice, fact, log, audience, venue):
            continue
        kept.append(fact)
    return tuple(kept)


async def _gate_recalled(
    recalled: tuple[RecalledMemoryItem, ...],
    audience: frozenset[str],
    venue: str,
    log: IDisclosureLog | None,
) -> tuple[RecalledMemoryItem, ...]:
    kept: list[RecalledMemoryItem] = []
    for item in recalled:
        decision = gate_episode(item.card, audience, venue)
        if decision.allowed:
            kept.append(item)
            continue
        if log is not None:
            await log.log_disclosure(
                memory_kind="episodic", memory_id=item.card.card_id, venue=venue,
                audience=tuple(sorted(audience)), action="keep", reason=decision.reason,
            )
    return tuple(kept)


async def gate_frame(
    facts: tuple[SemanticFact, ...],
    recalled: tuple[RecalledMemoryItem, ...],
    audience: frozenset[str],
    venue: str,
    log: IDisclosureLog | None,
    *,
    working: IWorkingStateStore | None = None,
    bonds: dict[str, SocialBondProfile] | None = None,
) -> tuple[tuple[SemanticFact, ...], tuple[RecalledMemoryItem, ...]]:
    """Apply the hard gate and persona choice, logging refusals."""
    gated_facts = await _gate_facts(
        facts, audience, venue, log, working=working, bonds=bonds
    )
    gated_recalled = await _gate_recalled(recalled, audience, venue, log)
    return gated_facts, gated_recalled


async def load_bonds_for(
    reader: IMemoryReader, bond_store: IBondDepthStore | None, chat_key: str,
    uids: tuple[str, ...],
) -> dict[str, SocialBondProfile]:
    pairs = [(u, await reader.get_social_bond(chat_key, u)) for u in uids]
    return await attach(bond_store, {u: b for u, b in pairs if b is not None})


async def select_facts(
    semantic: SemanticMemoryRetriever | None,
    facts: tuple[SemanticFact, ...], query: str, limit: int,
    now_ms: int | None = None,
) -> tuple[SemanticFact, ...]:
    current = int(time.time() * 1000) if now_ms is None else now_ms
    if semantic is None:
        return tuple(unified_rank(facts, query, {}, {}, current)[:limit])
    ranked = await semantic.rank_fused(facts, query, current)
    if ranked is not None:
        return tuple(ranked[:limit])
    relations = await semantic.boost_ids(facts, query, current)
    return tuple(unified_rank(facts, query, {}, relations, current)[:limit])


IncludedFact = tuple[int, str, str]


def included_facts(facts: tuple[SemanticFact, ...]) -> tuple[IncludedFact, ...]:
    return tuple(
        (fact.fact_id, fact.subject, fact.fact_text)
        for fact in facts if fact.scope == "person"
    )


def _overlaps(text: str, subject: str, body: str) -> bool:
    if len(subject) >= 2 and subject in text:
        return True
    clean = " ".join(body.split())
    return any(clean[i:i + 8] in text for i in range(max(0, len(clean) - 7)))


async def attribute_reply(
    text: str, included: tuple[IncludedFact, ...], venue: str,
    sender: str, log: IDisclosureLog | None,
) -> None:
    """D9: log a person fact as actually said when the reply overlaps it."""
    if log is None:
        return
    for fact_id, subject, body in included:
        if _overlaps(text, subject, body):
            await log.log_disclosure(
                memory_kind="semantic", memory_id=fact_id, venue=venue,
                audience=(sender,) if sender else (), action="said",
                reason="reply_overlap", phase="post",
            )


__all__ = [
    "attribute_reply", "audience_of", "consolidate_dialogue", "gate_frame",
    "included_facts", "load_facts", "recall_and_reinforce",
]
