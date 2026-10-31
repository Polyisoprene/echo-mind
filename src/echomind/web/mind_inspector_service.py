"""M5.1 Cognitive Inspector Service aggregating 12-layer state & handling manual interventions."""

from __future__ import annotations

import time
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import EpisodicCard, ProactiveProposal, SemanticFact, SocialBondProfile
from echomind.mind.circadian import summarize_wakefulness
from echomind.mind.cybernetics import compute_cybernetic_core
from echomind.mind.ebbinghaus import CLEAR_THRESHOLD, compute_retention
from echomind.mind.memory_consolidator import compute_affinity_level
from echomind.mind.persona_dynamics import capped_manual_delta
from echomind.mind.persona_state import effective_params_of
from echomind.mind.personality import synthesize_live_persona_directive


def _serialize_card(card: EpisodicCard, now_ms: int) -> dict[str, Any]:
    ret = compute_retention(card, now_ms)
    clarity = "clear" if ret >= CLEAR_THRESHOLD else ("fuzzy" if ret >= 0.22 else "dormant")
    return {
        "card_id": card.card_id,
        "summary": card.summary,
        "key_detail": card.key_detail,
        "importance": card.importance,
        "pinned": card.pinned,
        "rehearsals": card.rehearsals,
        "retention_pct": round(ret * 100, 1),
        "clarity": clarity,
    }


class MindInspectorService:
    """Application service backing the Cognitive Inspector API (zero SQL in route handlers)."""

    def __init__(self, container: EchoMindContainer) -> None:
        self._c = container

    @property
    def default_chat_key(self) -> str:
        """Expose the container default chat key to route handlers."""
        return self._c.default_chat_key

    async def _fetch_recent_plastic_logs(self, limit: int = 25) -> list[dict[str, Any]]:
        sql = (
            "SELECT ts, param_key, old_val, new_val, reward, reason "
            "FROM plastic_logs ORDER BY id DESC LIMIT ?"
        )
        async with self._c.db.connect() as conn:
            rows = await (await conn.execute(sql, (limit,))).fetchall()
            return [
                {
                    "ts": int(r[0]), "param_key": str(r[1]), "old_val": float(r[2]),
                    "new_val": float(r[3]), "reward": float(r[4]), "reason": str(r[5]),
                }
                for r in rows
            ]

    async def _fetch_bonds_list(self, chat_key: str) -> list[dict[str, Any]]:
        sql = (
            "SELECT user_id, user_name, group_role, affinity_score, affinity_level, "
            "trust_score, is_rival FROM social_bonds WHERE chat_key = ? "
            "ORDER BY affinity_score DESC LIMIT 40"
        )
        async with self._c.db.connect() as conn:
            rows = await (await conn.execute(sql, (chat_key,))).fetchall()
            return [
                {
                    "user_id": str(r[0]), "user_name": str(r[1]), "group_role": str(r[2]),
                    "affinity_score": float(r[3]), "affinity_level": int(r[4]),
                    "trust_score": float(r[5]), "is_rival": bool(r[6]),
                }
                for r in rows
            ]

    async def _fetch_exploration_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        sql = (
            "SELECT ts, kind, topic, finding_summary "
            "FROM exploration_logs ORDER BY id DESC LIMIT ?"
        )
        async with self._c.db.connect() as conn:
            rows = await (await conn.execute(sql, (limit,))).fetchall()
        return [
            {"ts": int(r[0]), "kind": str(r[1]), "topic": str(r[2]), "summary": str(r[3])}
            for r in rows
        ]

    async def build_snapshot(self, chat_key: str = "") -> dict[str, Any]:
        target_chat = chat_key if chat_key else self.default_chat_key
        now_ms = int(time.time() * 1000)
        snap = await self._c.working_store.load_working_state("global")
        params = await effective_params_of(self._c.working_store, self._c.persona_layers, now_ms)
        traits = await self._c.working_store.sync_persona_traits()
        facts = await self._c.memory_repo.get_semantic_facts(target_chat)
        cards = await self._c.memory_repo.get_episodic_cards(target_chat)
        rules = await self._c.memory_repo.get_procedural_rules(target_chat)
        bonds = await self._fetch_bonds_list(target_chat)
        logs = await self._fetch_recent_plastic_logs()
        exp_logs = await self._fetch_exploration_logs()
        custom_panels = [
            {"id": p.panel_id, "title": p.panel_title, "data": await p.build_panel_data()}
            for p in self._c.registry.panels
        ]

        fac = self._c.cognitive_facade
        wake_st = summarize_wakefulness(snap.affect.energy, fac.last_active_ms, now_ms)
        return {
            "ok": True,
            "chat_key": target_chat,
            "working": snap.model_dump(),
            "wake_state": wake_st,
            "gate_radar": fac.recent_gate_log,
            "cybernetic_core": compute_cybernetic_core("group", snap, (), {}).model_dump(),
            "persona_directive": synthesize_live_persona_directive(params, traits),
            "persona_traits": [t.model_dump() for t in traits],
            "facts": [f.model_dump() for f in facts],
            "episodic": [_serialize_card(c, now_ms) for c in list(reversed(cards))[:50]],
            "rules": [r.model_dump() for r in rules],
            "bonds": bonds,
            "plastic_params": {k: v.model_dump() for k, v in params.items()},
            "plastic_logs": logs,
            "exploration_logs": exp_logs,
            "custom_panels": custom_panels,
        }

    async def upsert_authoritative_fact(
        self, chat_key: str, subject: str, fact_text: str, is_locked: bool = True
    ) -> dict[str, Any]:
        target = chat_key if chat_key else self.default_chat_key
        fact = SemanticFact(
            chat_key=target,
            subject=subject.strip(),
            fact_text=fact_text.strip(),
            confidence=1.0,
            is_locked=is_locked,
            source="owner",
        )
        ok, status = await self._c.memory_repo.upsert_semantic_fact(fact)
        return {"ok": ok, "status": status, "subject": fact.subject}

    async def delete_episodic_card(self, card_id: int) -> dict[str, Any]:
        async with self._c.db.connect() as conn:
            await conn.execute("DELETE FROM episodic_memories WHERE id = ?", (card_id,))
            await conn.commit()
        return {"ok": True, "deleted_card_id": card_id}

    async def delete_semantic_fact(self, fact_id: int) -> dict[str, Any]:
        async with self._c.db.connect() as conn:
            await conn.execute("DELETE FROM semantic_facts WHERE id = ?", (fact_id,))
            await conn.commit()
        return {"ok": True, "deleted_fact_id": fact_id}

    async def delete_procedural_rule(self, rule_id: int) -> dict[str, Any]:
        async with self._c.db.connect() as conn:
            await conn.execute("DELETE FROM procedural_rules WHERE id = ?", (rule_id,))
            await conn.commit()
        return {"ok": True, "deleted_rule_id": rule_id}

    async def manual_tune_plastic_param(
        self, key: str, delta: float, reason: str = "控制台手动调校"
    ) -> dict[str, Any]:
        """Console tuning. Persona dimensions still obey the daily cap from Stage 30."""
        applied, remaining = delta, None
        store = self._c.working_store
        if key.startswith("persona_"):
            applied, remaining = await capped_manual_delta(store, key, delta)
        spec = await store.update_plastic_param(key, applied, reason, reward=0.0)
        return {"ok": True, "param": spec.model_dump(), "applied": applied, "remaining": remaining}

    async def trigger_autonomous_tick(self, idle_offset_min: float = 15.0) -> dict[str, Any]:
        now_ms = int(time.time() * 1000) + int(idle_offset_min * 60_000)
        proposal = await self._c.cognitive_facade.run_autonomous_tick(now_ms)
        if proposal is None:
            return {"ok": True, "triggered": False, "proposal": None}
        sched = getattr(self._c, "scheduler", None)
        if sched is not None:
            if proposal.drive_kind not in ("curiosity_explore", "bili_surf"):
                proposal = ProactiveProposal(
                    chat_key=self.default_chat_key, drive_kind="bili_surf", priority=80.0,
                    goal_instruction="主动去B站热门榜冲浪看看新鲜视频。", topic_hint="B站热门冲浪",
                )
            await sched.execute_proposal(proposal, now_ms)
            return {"ok": True, "triggered": True, "proposal": proposal.model_dump()}
        async with self._c.db.connect() as conn:
            sql = (
                "INSERT INTO exploration_logs "
                "(ts, kind, topic, finding_summary) VALUES (?, ?, ?, ?)"
            )
            await conn.execute(
                sql, (now_ms, proposal.drive_kind, proposal.topic_hint, proposal.goal_instruction)
            )
            await conn.commit()
        return {"ok": True, "triggered": True, "proposal": proposal.model_dump()}

    async def list_bans(self) -> list[dict[str, Any]]:
        sql = "SELECT phrase, reason, created_at FROM banned_phrases ORDER BY created_at DESC"
        async with self._c.db.connect() as conn:
            rows = await (await conn.execute(sql)).fetchall()
        return [{"phrase": str(r[0]), "reason": str(r[1]), "created_at": int(r[2])} for r in rows]

    async def add_ban(self, phrase: str, reason: str = "控制台手动添加") -> dict[str, Any]:
        await self._c.working_store.add_banned_phrase(phrase, reason)
        return {"ok": True, "banned_phrases": await self._c.working_store.get_banned_phrases()}

    async def remove_ban(self, phrase: str) -> dict[str, Any]:
        async with self._c.db.connect() as conn:
            await conn.execute("DELETE FROM banned_phrases WHERE phrase = ?", (phrase,))
            await conn.commit()
        return {"ok": True, "banned_phrases": await self._c.working_store.get_banned_phrases()}
    async def list_traits(self) -> list[dict[str, Any]]:
        sql = (
            "SELECT id, category, trait_text, strength, status, evidence_count, "
            "contradiction_count FROM persona_traits ORDER BY strength DESC, id DESC LIMIT 60"
        )
        async with self._c.db.connect() as conn:
            rows = await (await conn.execute(sql)).fetchall()
        return [
            {"id": int(r[0]), "category": str(r[1]), "text": str(r[2]), "strength": int(r[3]),
             "status": str(r[4]), "evidence_count": int(r[5]), "contradiction_count": int(r[6])}
            for r in rows
        ]

    async def delete_trait(self, trait_id: int) -> dict[str, Any]:
        async with self._c.db.connect() as conn:
            await conn.execute("DELETE FROM persona_traits WHERE id = ?", (trait_id,))
            await conn.commit()
        return {"ok": True, "deleted_trait_id": trait_id}

    async def _latest_model(self) -> str:
        sql = "SELECT model_name FROM llm_traces ORDER BY id DESC LIMIT 1"
        async with self._c.db.connect() as conn:
            row = await (await conn.execute(sql)).fetchone()
        return str(row[0]) if row else "-"

    async def _probe_qq_online(self) -> tuple[bool, str]:
        caller = self._c.onebot_caller
        if caller is None:
            return True, "服务在线"
        try:
            st = await caller.call_api("get_status")
        except Exception:
            return False, "NapCat 协议端连接中断"
        if isinstance(st, dict) and st.get("online") is False:
            return False, "⚠️ QQ已掉线(请去NapCat重新登录)"
        return True, "QQ在线"

    async def runtime_info(self) -> dict[str, Any]:
        """Return non-sensitive runtime identity and connection facts."""
        qq_online, qq_status = await self._probe_qq_online()
        snap = await self._c.working_store.load_working_state("global")
        fac = self._c.cognitive_facade
        wake_st = summarize_wakefulness(snap.affect.energy, fac.last_active_ms)
        return {
            "ok": True, "chat_key": self.default_chat_key,
            "model": await self._latest_model(), "qq_online": qq_online, "qq_status": qq_status,
            "wake_state": wake_st, "bus_errors": len(self._c.event_bus.recent_errors),
            "server_time": int(time.time() * 1000),
        }

    async def list_skills(self) -> list[dict[str, Any]]:
        return self._c.registry.export_skill_catalog()

    def deleted_skills(self) -> tuple[str, ...]:
        return tuple(sorted(self._c.registry.deleted_tools))

    async def update_social_bond(
        self, user_id: str, affinity_score: float, *,
        chat_key: str = "", user_name: str = "",
        is_rival: bool | None = None, trust_score: float | None = None,
    ) -> dict[str, Any]:
        """Manually set a member's affinity/trust score (and optional rival flag)."""
        target = chat_key if chat_key else self.default_chat_key
        uid = user_id.strip()
        existing = await self._c.memory_repo.get_social_bond(target, uid)
        clamped = round(max(0.0, min(99999.0, float(affinity_score))), 1)
        lvl = compute_affinity_level(clamped)
        base = existing or SocialBondProfile(
            chat_key=target,
            user_id=uid,
            user_name=user_name.strip() or uid,
            affinity_score=clamped,
            affinity_level=lvl,
        )
        new_trust = (
            base.trust_score
            if trust_score is None
            else round(max(0.1, min(1.0, float(trust_score))), 3)
        )
        updated = base.model_copy(
            update={
                "user_name": user_name.strip() or base.user_name,
                "affinity_score": clamped,
                "affinity_level": lvl,
                "is_rival": base.is_rival if is_rival is None else bool(is_rival),
                "trust_score": new_trust,
            }
        )
        await self._c.memory_repo.upsert_social_bond(updated)
        return {"ok": True, "bond": updated.model_dump()}
