"""M14.1~M14.3 Cybernetic Self-Organizing Core (Haken Order Parameters),
Ashby Two-Stage Selection Amplifier (HippoRAG 2-Hop Flotation) & A-MEM Schema Crystallizer.
"""

from __future__ import annotations

import re

from echomind.domain.models import (
    CyberneticCoreState,
    EpisodicCard,
    Percept,
    ProactiveProposal,
    SemanticFact,
    SocialBondProfile,
    WorkingSnapshot,
)

BILI_OR_MEDIA_RE = re.compile(
    r"BV[0-9A-Za-z]{10}|b23\.tv|bilibili\.com|\[图片\]|\[视频\]|\[语音|\[合并转发|转发"
)
SEARCH_OR_FACT_RE = re.compile(r"是什么|为什么|怎么回事|热梗|搜一下|查一下|B站|热门|新闻")
VOICE_OR_SING_RE = re.compile(r"唱首|唱歌|来首歌|翻唱|发语音|说句话|听你声音|晚安|早安")
SOCIAL_CHECK_RE = re.compile(r"群主|管理员|群成员|谁是|记住|说说|空间|签名")

REAGENT_TOOLS: dict[str, tuple[str, ...]] = {
    "日常轻装剂": ("send_message", "send_sticker", "feiyu_say", "recall_memory"),
    "多模态鉴赏剂": (
        "look_at_image",
        "watch_video",
        "read_voice",
        "bili_video",
        "read_forward",
    ),
    "百科求真剂": ("recall_memory", "meme_wiki", "web_search", "bili_search", "bili_popular"),
    "声情共鸣与点歌剂": ("feiyu_say", "feiyu_cover", "send_sticker", "send_poke"),
    "社交防忽悠核查剂": (
        "recall_memory",
        "get_group_members",
        "memory_append",
        "qzone_publish",
        "profile_signature",
    ),
}
SCHEMA_IGNORE_KEYS = frozenset(
    {
        "回音", "主人", "群友", "今天", "刚才", "视频", "图片", "消息",
        "大家", "聊天", "觉得", "一个", "qq", "群聊", "群主", "自己",
    }
)
CONCEPT_TOKEN_RE = re.compile(r"[\u4e00-\u9fa5]{2,5}|[A-Za-z0-9]{2,12}")


def _card_concepts(card: EpisodicCard) -> tuple[str, ...]:
    raw = f"{card.key_detail} {card.summary}"
    tokens = [
        m.lower()
        for m in CONCEPT_TOKEN_RE.findall(raw)
        if m.lower() not in SCHEMA_IGNORE_KEYS and not m.isdigit()
    ]
    return tuple(dict.fromkeys(tokens))


def _clamp(val: float, lo: float, hi: float) -> float:
    return round(max(lo, min(hi, val)), 3)


def _compute_stance_order(
    snap: WorkingSnapshot,
    triggers: tuple[Percept, ...],
    bonds_map: dict[str, SocialBondProfile],
    owner_qq: str,
    has_conflict: bool,
) -> float:
    aff = snap.affect
    uid = triggers[-1].sender_id if triggers else ""
    bond = bonds_map.get(uid)
    bond_pull = ((bond.affinity_level / 5.0) * bond.trust_score) if bond else 0.35
    owner_bonus = 0.35 if (owner_qq and uid == owner_qq) else 0.0
    mood_pull = aff.valence / 220.0
    penalty = (aff.irritation / 95.0) + (0.35 if has_conflict else 0.0)
    return _clamp(bond_pull + owner_bonus + mood_pull - penalty, -1.0, 1.0)


def _compute_epistemic_order(
    snap: WorkingSnapshot,
    joined_text: str,
    unknown_count: int,
    has_conflict: bool,
) -> float:
    cur_base = snap.drives.curiosity / 200.0
    unk_boost = min(0.45, unknown_count * 0.25)
    conf_boost = 0.35 if has_conflict else 0.0
    q_boost = 0.25 if SEARCH_OR_FACT_RE.search(joined_text) else 0.0
    return _clamp(cur_base + unk_boost + conf_boost + q_boost, 0.0, 1.0)


def _compute_modality_order(
    snap: WorkingSnapshot, scene: str, joined_text: str
) -> float:
    aff = snap.affect
    arousal = (abs(aff.valence) * 0.35 + aff.jealousy * 1.1 + aff.shyness * 0.9) / 110.0
    priv_bonus = 0.18 if scene == "private" else 0.0
    voice_boost = 0.48 if VOICE_OR_SING_RE.search(joined_text) else 0.0
    return _clamp(arousal + priv_bonus + voice_boost, 0.0, 1.0)


def _derive_regime_label(stance: float, epistemic: float, modality: float) -> str:
    if epistemic >= 0.55 and stance < 0.0:
        return "🛡️ 审慎防忽悠核查态"
    if epistemic >= 0.55:
        return "🔍 好奇考据求真态"
    if modality >= 0.58 and stance >= 0.35:
        return "🎙️ 亲昵声情共鸣态"
    if stance <= -0.25:
        return "💢 刺头防御呛声态"
    if stance >= 0.45:
        return "💖 偏心护短粘人态"
    return "🌿 日常熟稔接梗态"


def _select_reagents(
    triggers: tuple[Percept, ...],
    joined_text: str,
    epistemic: float,
    modality: float,
    has_conflict: bool,
) -> tuple[str, ...]:
    reagents: list[str] = ["日常轻装剂"]
    has_media = any(p.media for p in triggers) or bool(BILI_OR_MEDIA_RE.search(joined_text))
    if has_media:
        reagents.append("多模态鉴赏剂")
    if epistemic >= 0.48 or SEARCH_OR_FACT_RE.search(joined_text):
        reagents.append("百科求真剂")
    if modality >= 0.52 or VOICE_OR_SING_RE.search(joined_text):
        reagents.append("声情共鸣与点歌剂")
    if has_conflict or SOCIAL_CHECK_RE.search(joined_text):
        reagents.append("社交防忽悠核查剂")
    return tuple(dict.fromkeys(reagents))


def compute_cybernetic_core(
    scene: str,
    snap: WorkingSnapshot,
    triggers: tuple[Percept, ...],
    bonds_map: dict[str, SocialBondProfile],
    *,
    owner_qq: str = "",
    unknown_terms: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> CyberneticCoreState:
    """Compute Haken's 3 Order Parameters & Ashby's Stage-1 Selected Reagents/Tools."""
    joined = " ".join(p.text for p in triggers)
    has_conflict = any("防忽悠" in w or "可信度" in w for w in warnings)
    stance = _compute_stance_order(snap, triggers, bonds_map, owner_qq, has_conflict)
    epistemic = _compute_epistemic_order(snap, joined, len(unknown_terms), has_conflict)
    modality = _compute_modality_order(snap, scene, joined)
    reagents = _select_reagents(triggers, joined, epistemic, modality, has_conflict)
    tools: list[str] = []
    for r_name in reagents:
        tools.extend(REAGENT_TOOLS.get(r_name, ()))
    temp = _clamp(0.70 - 0.22 * epistemic + 0.12 * modality, 0.35, 0.90)
    return CyberneticCoreState(
        stance_order=stance,
        epistemic_order=epistemic,
        modality_order=modality,
        core_regime=_derive_regime_label(stance, epistemic, modality),
        active_reagents=reagents,
        selected_tools=tuple(dict.fromkeys(tools)),
        recommended_temperature=round(temp, 2),
    )


def render_cybernetic_core_directive(core: CyberneticCoreState) -> str:
    """Render the Order Parameter Core state into a compact cognitive frame directive."""
    reagent_str = " + ".join(f"🧪{r}" for r in core.active_reagents)
    return (
        f"- 🧭 自组织核心磁针（Order Parameters）：【{core.core_regime}】"
        f"（姿态核={core.stance_order:+.2f} ｜ 求真核={core.epistemic_order:.2f} "
        f"｜ 声情模态核={core.modality_order:.2f}）\n"
        f"- 🔬 智力放大选矿剂：{reagent_str}（推荐采样温度 T={core.recommended_temperature}）"
    )


def _extract_seed_concepts(
    cards: tuple[EpisodicCard, ...], q_low: str, uid_set: frozenset[str]
) -> dict[str, float]:
    seed_concepts: dict[str, float] = {}
    for card in cards:
        concepts = _card_concepts(card)
        kw_hits = len([k for k in concepts if k in q_low])
        u_hits = len([u for u in card.participants if u in uid_set])
        weight = min(1.0, kw_hits * 0.45 + u_hits * 0.30)
        if weight <= 0.0:
            continue
        for kw in concepts:
            seed_concepts[kw] = max(seed_concepts.get(kw, 0.0), weight)
    return seed_concepts


def compute_associative_flotation_boosts(
    cards: tuple[EpisodicCard, ...],
    query_text: str,
    active_user_ids: tuple[str, ...],
    damping: float = 0.45,
) -> dict[int, float]:
    """HippoRAG (NeurIPS 2024) 2-Hop Personalized PageRank / Spreading Activation over memory."""
    seeds = _extract_seed_concepts(cards, query_text.lower(), frozenset(active_user_ids))
    if not seeds:
        return {}
    boosts: dict[int, float] = {}
    for card in cards:
        concepts = _card_concepts(card)
        propagated = sum([seeds.get(kw, 0.0) for kw in concepts])
        if propagated > 0.0:
            boosts[card.card_id] = round(min(0.65, damping * propagated), 4)
    return boosts


def _group_cards_by_concept(cards: tuple[EpisodicCard, ...]) -> dict[str, list[EpisodicCard]]:
    clusters: dict[str, list[EpisodicCard]] = {}
    pairs = [(card, kw) for card in cards for kw in _card_concepts(card)]
    for card, clean in pairs:
        if len(clean) >= 2:
            clusters.setdefault(clean, []).append(card)
    return clusters


def crystallize_self_organizing_schemas(
    chat_key: str,
    cards: tuple[EpisodicCard, ...],
    existing_facts: tuple[SemanticFact, ...],
) -> tuple[SemanticFact, ...]:
    """A-MEM (NeurIPS 2025) Zettelkasten self-organizing schema crystallization."""
    existing_subjects = {f.subject for f in existing_facts}
    clusters = _group_cards_by_concept(cards)
    new_schemas: list[SemanticFact] = []
    for concept, group in clusters.items():
        subj = f"自组织图式:{concept[:18]}"
        mass = sum(c.importance + c.rehearsals * 0.8 for c in group)
        if len(group) < 2 or subj in existing_subjects or mass < 4.5:
            continue
        snippets = "；".join(c.summary[:34] for c in group[-3:])
        new_schemas.append(
            SemanticFact(
                chat_key=chat_key,
                subject=subj,
                fact_text=f"围绕『{concept}』自组织聚合的{len(group)}段经历：{snippets}",
                confidence=0.86,
                source="explored",
            )
        )
    return tuple(new_schemas[:3])


def consume_proposal_snapshot(
    snap: WorkingSnapshot, proposal: ProactiveProposal
) -> WorkingSnapshot:
    """Satiate internal drives after an autonomous proposal is triggered."""
    drv = snap.drives
    if proposal.drive_kind == "curiosity_explore":
        rem = snap.curiosity_queue[1:] if snap.curiosity_queue else ()
        nd = drv.model_copy(update={"curiosity": max(15.0, drv.curiosity - 25.0)})
        return snap.model_copy(update={"curiosity_queue": rem, "drives": nd})
    if proposal.drive_kind == "jealousy_poke":
        nj = min(20.0, max(0.0, round(drv.jealousy_drive - 35.0, 2)))
        aff = snap.affect.model_copy(update={"jealousy": nj})
        nd = drv.model_copy(update={"jealousy_drive": nj})
        return snap.model_copy(update={"affect": aff, "drives": nd})
    nd = drv.model_copy(
        update={
            "curiosity": max(20.0, round(drv.curiosity - 22.0, 2)),
            "social_expression": max(15.0, round(drv.social_expression - 25.0, 2)),
        }
    )
    return snap.model_copy(update={"drives": nd})
