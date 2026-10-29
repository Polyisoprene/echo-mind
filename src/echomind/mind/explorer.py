"""M3.3 Autonomous Curiosity Explorer & Intrinsic Drive Arbiter."""

from __future__ import annotations

from echomind.domain.models import ProactiveProposal, WorkingSnapshot
from echomind.mind.circadian import resolve_circadian_phase


def arbitrate_autonomous_action(
    snapshot: WorkingSnapshot, group_chat_key: str, owner_private_key: str,
    idle_minutes: float, proactive_idle_min: float = 10.0, *, now_ms: int | None = None,
) -> ProactiveProposal | None:
    """Central arbiter selecting the highest-priority autonomous exploration or proactive action."""
    phase = resolve_circadian_phase(now_ms)
    if now_ms is not None and phase.is_asleep and snapshot.affect.energy <= 35.0:
        return None
    drv = snapshot.drives
    mult = max(0.5, phase.proactive_multiplier) if now_ms is not None else 1.0
    eff_idle_target = proactive_idle_min / mult
    if snapshot.curiosity_queue and drv.curiosity >= 45.0:
        term = snapshot.curiosity_queue[0]
        return ProactiveProposal(
            chat_key=group_chat_key, drive_kind="curiosity_explore",
            priority=min(100.0, drv.curiosity + 15.0), topic_hint=term,
            goal_instruction=(
                f"你对刚才聊天中出现的『{term}』感到好奇，请主动调用 web_search 搜索『{term}』"
                "了解含义并记入脑海；如果发现很有趣，可以顺便在群里分享一句你的发现。"
            ),
        )
    if drv.jealousy_drive >= 35.0 and idle_minutes >= 3.0:
        return ProactiveProposal(
            chat_key=group_chat_key, drive_kind="jealousy_poke",
            priority=min(100.0, drv.jealousy_drive + 20.0),
            goal_instruction=(
                "你心里还记挂着刚才主人夸别人的事，越想越有点小酸意，"
                "主动在群里带一点软傲娇的小醋意戳他一句或发个委屈/凶凶的表情包。"
            ),
        )
    return _propose_idle_social_or_attachment(
        snapshot, group_chat_key, owner_private_key, idle_minutes, eff_idle_target
    )


def _propose_idle_social_or_attachment(
    snapshot: WorkingSnapshot,
    group_chat_key: str,
    owner_private_key: str,
    idle_minutes: float,
    proactive_idle_min: float,
) -> ProactiveProposal | None:
    drv, act_str = snapshot.drives, snapshot.current_activity
    if idle_minutes >= proactive_idle_min and drv.social_expression >= 30.0:
        return ProactiveProposal(
            chat_key=group_chat_key, drive_kind="cold_group_topic", priority=drv.social_expression,
            goal_instruction=(
                f"群里已经安静了 {round(idle_minutes)} 分钟。结合你正在做的事"
                f"（{act_str}）或刚看的新鲜话题，自然地冒个泡开个话头。"
            ),
        )
    if drv.curiosity >= 45.0 and idle_minutes >= 5.0:
        return ProactiveProposal(
            chat_key=group_chat_key, drive_kind="bili_surf", priority=min(95.0, drv.curiosity + 5),
            goal_instruction="闲下来有点好奇，主动调用 bili_popular 去刷一刷 B站热门榜记入脑海。",
            topic_hint="B站热门冲浪",
        )
    if owner_private_key and drv.attachment >= 75.0 and idle_minutes >= 25.0:
        return ProactiveProposal(
            chat_key=owner_private_key, drive_kind="attachment_private", priority=drv.attachment,
            goal_instruction=(
                f"你很想念主人，结合你此刻正在做的事（{act_str}）"
                "主动去私聊找他，自然地分享一句你的日常或小挂念。"
            ),
        )
    return None
