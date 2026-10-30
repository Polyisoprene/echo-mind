"""SQLite implementation of IMemoryReader and IMemoryWriter with anti-spoofing fact lock."""

from __future__ import annotations

import json
import time
from typing import Any, Literal, cast

import aiosqlite

from echomind.adapters.storage.claim_repo import mirror_fact
from echomind.adapters.storage.claim_views import facts_v2_enabled, load_claim_facts
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import (
    EpisodicCard,
    ProceduralRule,
    SemanticFact,
    SocialBondProfile,
)

SourceType = Literal["system", "owner", "explored", "peer"]
RoleType = Literal["owner", "admin", "member"]


def _row_to_episodic(row: aiosqlite.Row) -> EpisodicCard:
    parts = json.loads(str(row[6] or "[]"))
    return EpisodicCard(
        card_id=int(row[0]),
        chat_key=str(row[1]),
        timestamp_ms=int(row[2]),
        msg_seq=int(row[3]),
        summary=str(row[4]),
        key_detail=str(row[5]),
        participants=tuple(str(p) for p in parts if p),
        importance=float(row[7]),
        pinned=bool(row[8]),
        rehearsals=int(row[9]),
        last_recalled_ms=int(row[10]),
    )


def _row_to_fact(row: aiosqlite.Row) -> SemanticFact:
    raw_src = str(row[6])
    src: SourceType = (
        cast(SourceType, raw_src) if raw_src in ("system", "owner", "explored", "peer") else "peer"
    )
    return SemanticFact(
        fact_id=int(row[0]),
        chat_key=str(row[1]),
        subject=str(row[2]),
        fact_text=str(row[3]),
        confidence=float(row[4]),
        is_locked=bool(row[5]),
        source=src,
        revision_count=int(row[7]),
    )


def _row_to_rule(row: aiosqlite.Row) -> ProceduralRule:
    return ProceduralRule(
        rule_id=int(row[0]),
        chat_key=str(row[1]),
        trigger_keyword=str(row[2]),
        trigger_user_id=str(row[3]),
        action_instruction=str(row[4]),
        strength=int(row[5]),
    )


def _row_to_bond(row: aiosqlite.Row) -> SocialBondProfile:
    raw_role = str(row[3])
    role: RoleType = (
        cast(RoleType, raw_role) if raw_role in ("owner", "admin", "member") else "member"
    )
    traits = json.loads(str(row[11] or "[]"))
    return SocialBondProfile(
        chat_key=str(row[0]),
        user_id=str(row[1]),
        user_name=str(row[2]),
        group_role=role,
        affinity_score=float(row[4]),
        affinity_level=int(row[5]),
        msg_count=int(row[6]),
        trust_score=float(row[7]),
        bond_depth=float(row[8]),
        is_rival=bool(row[9]),
        rival_reason=str(row[10]),
        traits=tuple(str(t) for t in traits if t),
    )


def _merge_evolving_fact_text(old_text: str, new_text: str) -> str:
    clean_new = new_text.strip()
    if not old_text:
        return clean_new
    clean_old = old_text.split("（此前曾是：")[0].strip()
    if not clean_old or clean_old == clean_new or clean_old in clean_new:
        return clean_new
    return f"{clean_new[:115]}（此前曾是：{clean_old[:28]}）"


class SqliteMemoryRepository:
    """Repository satisfying both IMemoryReader and IMemoryWriter protocols."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def get_episodic_cards(self, chat_key: str) -> tuple[EpisodicCard, ...]:
        sql = (
            "SELECT id, chat_key, ts, msg_seq, summary, key_detail, participants_json, "
            "importance, pinned, rehearsals, last_recalled_ms "
            "FROM episodic_memories WHERE chat_key = ? ORDER BY ts ASC"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key,))
            rows = await cursor.fetchall()
            return tuple(_row_to_episodic(r) for r in rows)

    async def get_semantic_facts(
        self, chat_key: str, min_confidence: float = 0.0
    ) -> tuple[SemanticFact, ...]:
        if facts_v2_enabled():
            return await load_claim_facts(self._db, chat_key)
        sql = (
            "SELECT id, chat_key, subject, fact_text, confidence, is_locked, "
            "source, revision_count "
            "FROM semantic_facts WHERE chat_key IN (?, 'global') AND confidence >= ? "
            "ORDER BY is_locked DESC, confidence DESC, id DESC"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key, min_confidence))
            rows = await cursor.fetchall()
            return tuple(_row_to_fact(r) for r in rows)

    async def get_procedural_rules(self, chat_key: str) -> tuple[ProceduralRule, ...]:
        sql = (
            "SELECT id, chat_key, trigger_keyword, trigger_user_id, action_instruction, strength "
            "FROM procedural_rules WHERE chat_key = ? ORDER BY strength DESC"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key,))
            rows = await cursor.fetchall()
            return tuple(_row_to_rule(r) for r in rows)

    async def get_social_bond(self, chat_key: str, user_id: str) -> SocialBondProfile | None:
        sql = (
            "SELECT chat_key, user_id, user_name, group_role, affinity_score, affinity_level, "
            "msg_count, trust_score, bond_depth, is_rival, rival_reason, traits_json "
            "FROM social_bonds WHERE chat_key = ? AND user_id = ?"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key, user_id))
            row = await cursor.fetchone()
            return _row_to_bond(row) if row else None

    async def get_rival_names(self, chat_key: str) -> tuple[str, ...]:
        sql = (
            "SELECT user_name, user_id FROM social_bonds "
            "WHERE chat_key IN (?, 'global') AND is_rival = 1"
        )
        async with self._db.connect() as conn:
            rows = await (await conn.execute(sql, (chat_key,))).fetchall()
        candidates = [str(col).strip() for r in rows for col in (r[0], r[1]) if str(col).strip()]
        return tuple(dict.fromkeys(candidates))

    async def save_episodic_card(self, card: EpisodicCard) -> int:
        sql = (
            "INSERT INTO episodic_memories "
            "(chat_key, ts, msg_seq, summary, key_detail, participants_json, importance, pinned, "
            "rehearsals, last_recalled_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            card.chat_key,
            card.timestamp_ms,
            card.msg_seq,
            card.summary,
            card.key_detail,
            json.dumps(list(card.participants), ensure_ascii=False),
            card.importance,
            int(card.pinned),
            card.rehearsals,
            card.last_recalled_ms or card.timestamp_ms,
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return int(cursor.lastrowid or 0)

    async def reinforce_episodic_card(self, card_id: int, recalled_ms: int) -> None:
        sql = (
            "UPDATE episodic_memories SET rehearsals = rehearsals + 1, last_recalled_ms = ? "
            "WHERE id = ?"
        )
        async with self._db.connect() as conn:
            await conn.execute(sql, (recalled_ms, card_id))
            await conn.commit()

    async def _check_fact_lock(
        self, conn: aiosqlite.Connection, fact: SemanticFact
    ) -> tuple[bool, int, str]:
        cursor = await conn.execute(
            "SELECT is_locked, revision_count, fact_text FROM semantic_facts "
            "WHERE chat_key = ? AND subject = ?",
            (fact.chat_key, fact.subject),
        )
        row = await cursor.fetchone()
        if not row:
            return False, 0, ""
        is_locked, rev, prev_txt = bool(row[0]), int(row[1]), str(row[2] or "")
        can_override = fact.source in ("system", "owner") and fact.is_locked
        return (is_locked and not can_override), rev, prev_txt

    async def upsert_semantic_fact(self, fact: SemanticFact) -> tuple[bool, str]:
        """Upsert a semantic fact with temporal change history & multi-evidence promotion."""
        now_ms = int(time.time() * 1000)
        async with self._db.connect() as conn:
            blocked, prev_rev, prev_txt = await self._check_fact_lock(conn, fact)
            if blocked:
                return False, "locked_fact_conflict"
            new_rev = prev_rev + 1
            eff_conf = max(fact.confidence, 0.85) if new_rev >= 2 else fact.confidence
            eff_txt = _merge_evolving_fact_text(prev_txt, fact.fact_text)
            sql = (
                "INSERT INTO semantic_facts "
                "(chat_key, subject, fact_text, confidence, is_locked, "
                "source, revision_count, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(chat_key, subject) DO UPDATE SET "
                "fact_text=excluded.fact_text, confidence=excluded.confidence, "
                "is_locked=excluded.is_locked, source=excluded.source, "
                "revision_count=excluded.revision_count, updated_at=excluded.updated_at"
            )
            await conn.execute(
                sql,
                (
                    fact.chat_key, fact.subject, eff_txt, eff_conf,
                    int(fact.is_locked), fact.source, new_rev, now_ms,
                ),
            )
            await conn.commit()
        await mirror_fact(
            self._db, chat_key=fact.chat_key, subject=fact.subject, value=eff_txt,
            source=fact.source, is_locked=fact.is_locked, now_ms=now_ms,
        )
        return True, "ok"

    async def upsert_procedural_rule(self, rule: ProceduralRule) -> int:
        sql = (
            "INSERT INTO procedural_rules "
            "(chat_key, trigger_keyword, trigger_user_id, action_instruction, strength) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(chat_key, trigger_keyword, trigger_user_id) DO UPDATE SET "
            "action_instruction=excluded.action_instruction, strength=excluded.strength"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                sql,
                (
                    rule.chat_key,
                    rule.trigger_keyword,
                    rule.trigger_user_id,
                    rule.action_instruction,
                    rule.strength,
                ),
            )
            await conn.commit()
            return int(cursor.lastrowid or 0)

    async def upsert_social_bond(self, bond: SocialBondProfile) -> None:
        sql = (
            "INSERT INTO social_bonds "
            "(chat_key, user_id, user_name, group_role, affinity_score, affinity_level, "
            "msg_count, trust_score, bond_depth, is_rival, rival_reason, traits_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(chat_key, user_id) DO UPDATE SET "
            "user_name=excluded.user_name, group_role=excluded.group_role, "
            "affinity_score=excluded.affinity_score, affinity_level=excluded.affinity_level, "
            "msg_count=excluded.msg_count, trust_score=excluded.trust_score, "
            "bond_depth=excluded.bond_depth, "
            "is_rival=excluded.is_rival, rival_reason=excluded.rival_reason, "
            "traits_json=excluded.traits_json"
        )
        traits_str = json.dumps(list(bond.traits), ensure_ascii=False)
        params: tuple[Any, ...] = (
            bond.chat_key,
            bond.user_id,
            bond.user_name,
            bond.group_role,
            bond.affinity_score,
            bond.affinity_level,
            bond.msg_count,
            bond.trust_score,
            bond.bond_depth,
            int(bond.is_rival),
            bond.rival_reason,
            traits_str,
        )
        async with self._db.connect() as conn:
            await conn.execute(sql, params)
            await conn.commit()
