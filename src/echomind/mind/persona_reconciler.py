"""M9.3 Persona-Memory Epistemic Conflict Reconciler (LLM-Driven, Zero-Hardcoding)."""

from __future__ import annotations

import json
import re
from typing import Any

from echomind.domain.models import (
    EpisodicCard,
    FrozenValueObject,
    PersonaTrait,
    ProceduralRule,
    SemanticFact,
)

JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")
RECONCILE_SYSTEM_PROMPT = "\n".join(
    [
        "你是认知智能体的「人设与记忆冲突审计中枢（Persona-Memory Conflict Auditor）」。",
        "运营者刚刚更新或确认了智能体的【最高宪法：当前基础人设卡】。请严格以该人设卡为唯一真理标准，"
        "审查下方存量的性格词条(traits)、条件反射规则(rules)、事实(facts)与往事记忆(cards)，找出所有：",
        "1. 【设定冲突项】：与当前基础人设的物种、身体部位、外貌或核心身份相违背的旧记忆/旧词条"
        "（例如：若当前人设是人类，但旧词条/规则/记忆里自称有非人尾巴/兽耳/鱼鳞等；"
        "反之若当前人设确实拥有该特征，则必须保留！）；",
        "2. 【跨主体串味与复读污染项】：把其他群友的专属设定套在自己身上，"
        "或围绕单一道具/食物/口头禅过度高频重复、导致祥林嫂式复读强迫症的污染条目；",
        "3. 【contradictionKeywords】：提炼出 0~8 个能够代表上述【与当前人设直接冲突的特征】或"
        "【重度复读污染】的特征词（每个词2~4字，用于在全量历史记忆中批量扫除同类冲突残余；"
        "注意：绝不能包含当前基础人设中合法拥有的特征词！）；",
        "4. 【newActivity】：写一句符合当前基础人设的全新日常待机状态"
        "（8~18字，替换掉过时的旧活动）。",
        "",
        "只输出严格合法的 JSON 对象：",
        '{"pruneTraitIds":[1,2],"pruneRuleIds":[3],"pruneFactIds":[4],"pruneCardIds":[5],'
        '"contradictionKeywords":["冲突词1","冲突词2"],"newActivity":"...","summaryReason":"..."}',
    ]
)


class ReconciliationPlan(FrozenValueObject):
    """Immutable LLM audit plan identifying memories that contradict the current persona."""

    prune_trait_ids: tuple[int, ...] = ()
    prune_rule_ids: tuple[int, ...] = ()
    prune_fact_ids: tuple[int, ...] = ()
    prune_card_ids: tuple[int, ...] = ()
    contradiction_keywords: tuple[str, ...] = ()
    new_activity: str = ""
    summary_reason: str = ""


def _fmt_traits(traits: tuple[PersonaTrait, ...]) -> list[str]:
    return [f"  - id={t.trait_id} [{t.category}]: {t.trait_text}" for t in traits[:40]]


def _fmt_rules(rules: tuple[ProceduralRule, ...]) -> list[str]:
    return [
        f"  - id={r.rule_id} [触发词:{r.trigger_keyword}]: {r.action_instruction}"
        for r in rules[:40]
    ]


def _fmt_facts(facts: tuple[SemanticFact, ...]) -> list[str]:
    return [
        f"  - id={f.fact_id} {f.subject}: {f.fact_text}"
        for f in facts[:40]
        if not f.is_locked and f.source != "system"
    ]


def _fmt_cards(cards: tuple[EpisodicCard, ...]) -> list[str]:
    return [f"  - id={c.card_id}: {c.summary} ({c.key_detail})" for c in cards[-45:]]


def build_reconcile_messages(
    role_text: str,
    traits: tuple[PersonaTrait, ...],
    rules: tuple[ProceduralRule, ...],
    facts: tuple[SemanticFact, ...],
    cards: tuple[EpisodicCard, ...],
    *,
    current_activity: str = "",
) -> list[dict[str, str]]:
    """Build the LLM prompt to audit memory stores against the authoritative role_text."""
    user_lines = [
        f"【最高宪法：当前基础人设卡】\n{role_text}",
        f"【当前工作记忆活动】\n{current_activity or '日常待机'}",
        "【存量性格词条 (traits)】",
        *(_fmt_traits(traits) or ["  (空)"]),
        "【存量条件反射规则 (rules)】",
        *(_fmt_rules(rules) or ["  (空)"]),
        "【存量语义事实 (facts)】",
        *(_fmt_facts(facts) or ["  (空)"]),
        "【近期海马体记忆采样 (cards)】",
        *(_fmt_cards(cards) or ["  (空)"]),
    ]
    return [
        {"role": "system", "content": RECONCILE_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def _int_tuple(raw_list: Any) -> tuple[int, ...]:
    if not isinstance(raw_list, list):
        return ()
    out: list[int] = []
    for item in raw_list:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return tuple(dict.fromkeys(out))


def _str_tuple(raw_list: Any, *, protected_text: str = "") -> tuple[str, ...]:
    if not isinstance(raw_list, list):
        return ()
    cleaned = [
        str(x).strip()
        for x in raw_list
        if len(str(x).strip()) >= 2 and str(x).strip() not in protected_text
    ]
    return tuple(dict.fromkeys(cleaned))[:10]


def parse_reconcile_plan(
    raw_content: str, *, role_text: str = "", bot_name: str = ""
) -> ReconciliationPlan:
    """Parse the LLM JSON output into an immutable ReconciliationPlan."""
    match = JSON_BLOCK_RE.search(raw_content)
    if not match:
        return ReconciliationPlan()
    try:
        data: dict[str, Any] = json.loads(match.group(0))
    except Exception:
        return ReconciliationPlan()
    if not isinstance(data, dict):
        return ReconciliationPlan()
    protected = f"{bot_name} {role_text}"
    return ReconciliationPlan(
        prune_trait_ids=_int_tuple(data.get("pruneTraitIds")),
        prune_rule_ids=_int_tuple(data.get("pruneRuleIds")),
        prune_fact_ids=_int_tuple(data.get("pruneFactIds")),
        prune_card_ids=_int_tuple(data.get("pruneCardIds")),
        contradiction_keywords=_str_tuple(
            data.get("contradictionKeywords"), protected_text=protected
        ),
        new_activity=str(data.get("newActivity", "")).strip()[:40],
        summary_reason=str(data.get("summaryReason", "")).strip()[:200],
    )


def matches_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    """Return True when text contains any LLM-identified contradiction keyword."""
    if not text or not keywords:
        return False
    return any(kw in text for kw in keywords if kw)
