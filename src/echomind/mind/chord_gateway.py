"""M28 chord gateway: probe gating, cooldown-aware wake decisions & turn chord resolution."""

from __future__ import annotations

from typing import Any

from echomind.domain.models import (
    AttentionDecision,
    Percept,
    SocialBondProfile,
    WorkingSnapshot,
)
from echomind.domain.ports import IWorkingStateStore
from echomind.mind.chord_cache import remember_chord
from echomind.mind.subconscious_probe import (
    SubconsciousChordProbe,
    SubconsciousChordResult,
    apply_chord_tensor_to_snapshot,
    evaluate_chord_wake_decision,
)

STRONG_SIGNAL_SCORE = 0.55


def format_recent(gate_log: list[dict[str, Any]], chat_key: str = "") -> tuple[str, ...]:
    """Render the recent gate-log tail as speaker lines, optionally scoped to one chat."""
    rows = [x for x in gate_log if not chat_key or x.get("chat_key") == chat_key]
    return tuple(f"{x.get('sender_name', '')}: {x.get('text', '')}" for x in rows[-6:])


def _is_probe_allowed(
    dec: AttentionDecision, percept: Percept, bond: SocialBondProfile | None
) -> bool:
    """Skip probing for direct summons, micro-signals and non-summoning rival bots."""
    if dec.tier == 1 or dec.salience_score <= 0.12:
        return False
    return not (bond is not None and bond.is_rival and not percept.is_called_by_name)


def _budget_allows(
    dec: AttentionDecision, clock: dict[str, int], percept: Percept, min_interval_ms: int
) -> bool:
    """Rate-limit ambient probes inside a burst, but always let strong signals through."""
    if dec.salience_score >= STRONG_SIGNAL_SCORE:
        return True
    last = clock.get(percept.chat_key, 0)
    return not (last > 0 and (percept.timestamp_ms - last) < min_interval_ms)


def _has_unseen(percept: Percept) -> bool:
    return any(not m.description for m in percept.media)


async def apply_probe_if_allowed(
    probe: SubconsciousChordProbe, percept: Percept, snap: WorkingSnapshot,
    dec: AttentionDecision, bond: SocialBondProfile | None, *,
    working: IWorkingStateStore, owner_qq: str,
    cache: dict[str, SubconsciousChordResult], recent_lines: tuple[str, ...] = (),
    in_ambient_cooldown: bool = False,
    probe_clock: dict[str, int] | None = None, min_probe_interval_ms: int = 0,
) -> tuple[WorkingSnapshot, AttentionDecision]:
    """Probe the subconscious chord when gated in; mood drifts now only if the turn stays silent."""
    if not _is_probe_allowed(dec, percept, bond):
        return snap, dec
    clock = probe_clock if probe_clock is not None else {}
    if not _budget_allows(dec, clock, percept, min_probe_interval_ms):
        return snap, dec
    clock[percept.chat_key] = percept.timestamp_ms
    chord = await probe.appraise(percept, recent_lines, bond)
    if chord is None:
        return snap, dec
    remember_chord(cache, percept.message_id, chord)
    new_dec = evaluate_chord_wake_decision(
        percept, chord, snap, _care_of(percept, owner_qq, bond),
        in_ambient_cooldown=in_ambient_cooldown, has_unseen=_has_unseen(percept),
    )
    if new_dec.should_wake:
        return snap, new_dec
    new_snap, _ = apply_chord_tensor_to_snapshot(snap, chord, percept, owner_qq, bond)
    await working.save_working_state(new_snap)
    return new_snap, new_dec


def _care_of(percept: Percept, owner_qq: str, bond: SocialBondProfile | None) -> float:
    from echomind.mind.drives import compute_care_weight

    return compute_care_weight(percept.sender_id, owner_qq, bond)


async def chord_for(
    probe: SubconsciousChordProbe | None, triggers: tuple[Percept, ...],
    bonds: dict[str, SocialBondProfile] | None,
    cache: dict[str, SubconsciousChordResult], dry_run: bool,
    *, timeout_s: float = 1.2,
) -> SubconsciousChordResult | None:
    """Resolve the turn chord, probing once when a direct summon skipped the gate probe."""
    if dry_run or not triggers:
        return None
    last = triggers[-1]
    cached = cache.get(last.message_id)
    if cached is not None:
        return cached
    if probe is None:
        return None
    bond = bonds.get(last.sender_id) if bonds else None
    if bond is not None and bond.is_rival and not last.is_called_by_name:
        return None
    chord = await probe.appraise(last, (), bond, timeout_s=timeout_s)
    if chord is not None:
        remember_chord(cache, last.message_id, chord)
    return chord
