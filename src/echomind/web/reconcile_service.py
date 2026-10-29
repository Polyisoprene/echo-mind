"""Application service executing LLM-driven Persona-Memory Conflict Reconciliation."""

from __future__ import annotations

from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import PersonaTrait
from echomind.mind.persona_reconciler import (
    ReconciliationPlan,
    build_reconcile_messages,
    matches_any_keyword,
    parse_reconcile_plan,
)

RECONCILE_SQL: dict[str, tuple[str, str]] = {
    "traits": (
        "SELECT id, trait_text FROM persona_traits",
        "DELETE FROM persona_traits WHERE id = ?",
    ),
    "rules": (
        "SELECT id, trigger_keyword, action_instruction FROM procedural_rules WHERE strength < 8",
        "DELETE FROM procedural_rules WHERE id = ? AND strength < 8",
    ),
    "facts": (
        "SELECT id, subject, fact_text FROM semantic_facts "
        "WHERE is_locked = 0 AND source != 'system'",
        "DELETE FROM semantic_facts WHERE id = ? AND is_locked = 0",
    ),
    "cards": (
        "SELECT id, summary, key_detail FROM episodic_memories",
        "DELETE FROM episodic_memories WHERE id = ?",
    ),
    "msgs": (
        "SELECT id, text FROM chat_messages WHERE is_self = 1",
        "DELETE FROM chat_messages WHERE id = ?",
    ),
}


def _extract_llm_content(resp: dict[str, Any]) -> str:
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    msg = first.get("message")
    return str(msg.get("content") or "") if isinstance(msg, dict) else ""


async def _load_all_traits(container: EchoMindContainer) -> tuple[PersonaTrait, ...]:
    sql = "SELECT id, category, trait_text, strength FROM persona_traits ORDER BY strength DESC"
    async with container.db.connect() as conn:
        cur = await conn.execute(sql)
        rows = await cur.fetchall()
    return tuple(
        PersonaTrait(trait_id=int(r[0]), category=r[1], trait_text=str(r[2]), strength=int(r[3]))
        for r in rows
    )


def _match_ids(rows: list[Any], explicit_ids: set[int], kws: tuple[str, ...]) -> list[int]:
    out: list[int] = []
    for row in rows:
        rid = int(row[0])
        text = " ".join(str(c) for c in row[1:])
        if rid in explicit_ids or matches_any_keyword(text, kws):
            out.append(rid)
    return out


async def _prune_table(
    conn: Any, sql_sel: str, sql_del: str, explicit_ids: set[int], kws: tuple[str, ...]
) -> int:
    rows = list(await (await conn.execute(sql_sel)).fetchall())
    target_ids = _match_ids(rows, explicit_ids, kws)
    for item_id in target_ids:
        await conn.execute(sql_del, (item_id,))
    return len(target_ids)


async def _apply_reconcile_plan(
    container: EchoMindContainer, plan: ReconciliationPlan
) -> dict[str, int]:
    kws = plan.contradiction_keywords
    t_ids, r_ids = set(plan.prune_trait_ids), set(plan.prune_rule_ids)
    f_ids, c_ids = set(plan.prune_fact_ids), set(plan.prune_card_ids)
    async with container.db.connect() as conn:
        n_t = await _prune_table(conn, *RECONCILE_SQL["traits"], t_ids, kws)
        n_r = await _prune_table(conn, *RECONCILE_SQL["rules"], r_ids, kws)
        n_f = await _prune_table(conn, *RECONCILE_SQL["facts"], f_ids, kws)
        n_c = await _prune_table(conn, *RECONCILE_SQL["cards"], c_ids, kws)
        n_m = await _prune_table(conn, *RECONCILE_SQL["msgs"], set(), kws)
        await conn.commit()
    return {
        "pruned_traits": n_t,
        "pruned_rules": n_r,
        "pruned_facts": n_f,
        "pruned_cards": n_c,
        "pruned_self_msgs": n_m,
    }


async def run_persona_reconciliation(
    container: EchoMindContainer, bot_name: str, role_text: str, chat_key: str = ""
) -> dict[str, Any]:
    """Audit and prune memories that conflict with the current base persona via LLM."""
    gw = container.llm_gateway
    if gw is None:
        return {"ok": False, "reason": "LLM 网关未初始化"}
    if not role_text.strip():
        return {"ok": False, "reason": "基础人设为空"}
    target = chat_key or container.default_chat_key
    traits = await _load_all_traits(container)
    rules = await container.memory_repo.get_procedural_rules(target)
    facts = await container.memory_repo.get_semantic_facts(target)
    cards = await container.memory_repo.get_episodic_cards(target)
    snap = await container.working_store.load_working_state("global")
    msgs = build_reconcile_messages(
        role_text, traits, rules, facts, cards, current_activity=snap.current_activity
    )
    resp = await gw.complete(msgs, temperature=0.2, max_tokens=900, chat_key="persona:reconcile")
    plan = parse_reconcile_plan(_extract_llm_content(resp), role_text=role_text, bot_name=bot_name)
    counts = await _apply_reconcile_plan(container, plan)
    if plan.new_activity:
        await container.working_store.save_working_state(
            snap.model_copy(update={"current_activity": plan.new_activity, "intentions": ()})
        )
    return {
        "ok": True,
        **counts,
        "contradiction_keywords": list(plan.contradiction_keywords),
        "new_activity": plan.new_activity,
        "summary_reason": plan.summary_reason,
    }
