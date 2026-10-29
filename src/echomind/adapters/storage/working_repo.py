"""SQLite implementation of IWorkingStateStore with 7D HEXACO personality & homeostatic bounds."""

from __future__ import annotations

import json
import time
from typing import Any, Literal, cast

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    IntentionItem,
    PersonaTrait,
    PlasticParamSpec,
    WorkingSnapshot,
)

TraitCategory = Literal["habit", "temperament", "taste", "taboo"]


def _spec(key: str, val: float, lo: float, hi: float, desc: str) -> PlasticParamSpec:
    return PlasticParamSpec(key=key, value=val, min_bound=lo, max_bound=hi, description=desc)


DEFAULT_PLASTIC_PARAMS: tuple[PlasticParamSpec, ...] = (
    _spec("talkativeness", 58.0, 20.0, 90.0, "群聊插话积极度"),
    _spec("proactive_idle_min", 10.0, 5.0, 30.0, "冷场主动开口等待分钟数"),
    _spec("skepticism", 55.0, 10.0, 95.0, "元认知防忽悠怀疑警觉度"),
    _spec("verify_impulse", 70.0, 20.0, 95.0, "遇到可疑断言主动调工具核验冲动"),
    _spec("curiosity_rate", 65.0, 20.0, 95.0, "好奇心增长率与主动搜索欲"),
    _spec("persona_warmth", 65.0, 15.0, 98.0, "性格维度：温柔粘人度 vs 清冷慢热度"),
    _spec("persona_tsundere", 62.0, 10.0, 95.0, "性格维度：依恋回避/傲娇嘴硬防备指数"),
    _spec("persona_playfulness", 58.0, 15.0, 95.0, "性格维度：古灵精怪玩梗吐槽度"),
    _spec("persona_possessiveness", 75.0, 20.0, 98.0, "性格维度：依恋焦虑/对主人的独占护食度"),
    _spec("persona_confidence", 55.0, 15.0, 95.0, "性格维度：社交自信笃定度 vs 害羞胆怯度"),
    _spec("persona_guile", 52.0, 10.0, 95.0, "HEXACO H轴反向：狡黠度/小机灵鬼撒谎与反忽悠倾向"),
    _spec("persona_defiance", 48.0, 10.0, 95.0, "Brehm逆反/HEXACO A轴反向：小刺头叛逆度"),
)

UPSERT_WORKING_SQL = (
    "INSERT INTO working_state "
    "(scope_key, valence, energy, jealousy, shyness, irritation, curiosity_drive, "
    "attachment_drive, jealousy_drive, social_drive, current_activity, inner_thought, "
    "intentions_json, curiosity_queue_json, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(scope_key) DO UPDATE SET "
    "valence=excluded.valence, energy=excluded.energy, jealousy=excluded.jealousy, "
    "shyness=excluded.shyness, irritation=excluded.irritation, "
    "curiosity_drive=excluded.curiosity_drive, attachment_drive=excluded.attachment_drive, "
    "jealousy_drive=excluded.jealousy_drive, social_drive=excluded.social_drive, "
    "current_activity=excluded.current_activity, inner_thought=excluded.inner_thought, "
    "intentions_json=excluded.intentions_json, "
    "curiosity_queue_json=excluded.curiosity_queue_json, updated_at=excluded.updated_at"
)


def _clamp_val(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _parse_intentions_json(raw_str: str) -> tuple[IntentionItem, ...]:
    items: list[dict[str, Any]] = json.loads(raw_str)
    return tuple(IntentionItem.model_validate(item) for item in items)


def _row_to_snapshot(scope_key: str, row: aiosqlite.Row | None) -> WorkingSnapshot:
    if row is None:
        return WorkingSnapshot(scope_key=scope_key)
    intents = _parse_intentions_json(str(row[11]))
    curiosity_q = tuple(str(x) for x in json.loads(str(row[12])))
    return WorkingSnapshot(
        scope_key=scope_key,
        affect=AffectiveVector(
            valence=float(row[0]),
            energy=float(row[1]),
            jealousy=float(row[2]),
            shyness=float(row[3]),
            irritation=float(row[4]),
        ),
        drives=DriveState(
            curiosity=float(row[5]),
            attachment=float(row[6]),
            jealousy_drive=float(row[7]),
            social_expression=float(row[8]),
        ),
        current_activity=str(row[9]),
        inner_thought=str(row[10]),
        intentions=intents,
        curiosity_queue=curiosity_q,
    )


def _row_to_trait(row: aiosqlite.Row) -> PersonaTrait:
    raw_cat = str(row[1])
    cat: TraitCategory = (
        cast(TraitCategory, raw_cat)
        if raw_cat in ("habit", "temperament", "taste", "taboo")
        else "habit"
    )
    return PersonaTrait(
        trait_id=int(row[0]),
        category=cat,
        trait_text=str(row[2]),
        strength=max(0, min(10, int(row[3]))),
    )


class SqliteWorkingStateStore:
    """Repository satisfying IWorkingStateStore with 7D personality & irritation persistence."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        self._defaults_ensured = False

    async def ensure_default_params(self) -> None:
        if self._defaults_ensured:
            return
        sql = (
            "INSERT OR IGNORE INTO plastic_params (key, value, min_bound, max_bound, description) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        async with self._db.connect() as conn:
            for s in DEFAULT_PLASTIC_PARAMS:
                await conn.execute(sql, (s.key, s.value, s.min_bound, s.max_bound, s.description))
            await conn.commit()
        self._defaults_ensured = True

    async def load_working_state(self, scope_key: str) -> WorkingSnapshot:
        sql = (
            "SELECT valence, energy, jealousy, shyness, irritation, curiosity_drive, "
            "attachment_drive, jealousy_drive, social_drive, current_activity, inner_thought, "
            "intentions_json, curiosity_queue_json FROM working_state WHERE scope_key = ?"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (scope_key,))
            return _row_to_snapshot(scope_key, await cursor.fetchone())

    async def save_working_state(self, snapshot: WorkingSnapshot) -> None:
        now_ms = int(time.time() * 1000)
        intents = json.dumps([i.model_dump() for i in snapshot.intentions], ensure_ascii=False)
        queue = json.dumps(list(snapshot.curiosity_queue), ensure_ascii=False)
        aff, drv = snapshot.affect, snapshot.drives
        row = (
            snapshot.scope_key,
            aff.valence,
            aff.energy,
            aff.jealousy,
            aff.shyness,
            aff.irritation,
            drv.curiosity,
            drv.attachment,
            drv.jealousy_drive,
            drv.social_expression,
            snapshot.current_activity,
            snapshot.inner_thought,
            intents,
            queue,
            now_ms,
        )
        async with self._db.connect() as conn:
            await conn.execute(UPSERT_WORKING_SQL, row)
            await conn.commit()

    async def get_plastic_params(self) -> dict[str, PlasticParamSpec]:
        await self.ensure_default_params()
        sql = "SELECT key, value, min_bound, max_bound, description FROM plastic_params"
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql)
            rows = await cursor.fetchall()
            return {
                str(r[0]): _spec(str(r[0]), float(r[1]), float(r[2]), float(r[3]), str(r[4]))
                for r in rows
            }

    async def update_plastic_param(
        self, key: str, delta: float, reason: str, reward: float
    ) -> PlasticParamSpec:
        params = await self.get_plastic_params()
        spec = params.get(key)
        if not spec:
            raise KeyError(f"Unknown plastic parameter: {key}")
        new_val = round(_clamp_val(spec.value + delta, spec.min_bound, spec.max_bound), 3)
        now_ms = int(time.time() * 1000)
        async with self._db.connect() as conn:
            await conn.execute("UPDATE plastic_params SET value = ? WHERE key = ?", (new_val, key))
            await conn.execute(
                "INSERT INTO plastic_logs (ts, param_key, old_val, new_val, reward, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now_ms, key, spec.value, new_val, reward, reason),
            )
            await conn.commit()
        return _spec(spec.key, new_val, spec.min_bound, spec.max_bound, spec.description)

    async def sync_persona_traits(
        self, new_trait: PersonaTrait | None = None, strength_delta: int = 0
    ) -> tuple[PersonaTrait, ...]:
        now_ms = int(time.time() * 1000)
        stale_cutoff = now_ms - 43_200_000  # 12h without reinforcement triggers decay
        async with self._db.connect() as conn:
            if strength_delta < 0:
                await conn.execute(
                    "UPDATE persona_traits SET strength = MAX(0, strength + ?)",
                    (strength_delta,),
                )
            await conn.execute(
                "UPDATE persona_traits SET strength = strength - 1, created_at = ? "
                "WHERE created_at > 0 AND created_at < ?",
                (now_ms, stale_cutoff),
            )
            await conn.execute("DELETE FROM persona_traits WHERE strength <= 0")
            if new_trait and new_trait.trait_text.strip():
                await conn.execute(
                    "INSERT INTO persona_traits (category, trait_text, strength, created_at) "
                    "VALUES (?, ?, ?, ?) ON CONFLICT(trait_text) DO UPDATE SET "
                    "strength = MIN(10, persona_traits.strength + 2), "
                    "created_at = excluded.created_at",
                    (new_trait.category, new_trait.trait_text.strip(), new_trait.strength, now_ms),
                )
            await conn.execute(
                "DELETE FROM persona_traits WHERE id NOT IN ("
                "SELECT id FROM persona_traits ORDER BY strength DESC, created_at DESC LIMIT 15)"
            )
            await conn.commit()
            cursor = await conn.execute(
                "SELECT id, category, trait_text, strength FROM persona_traits "
                "ORDER BY strength DESC, id DESC LIMIT 12"
            )
            return tuple(_row_to_trait(r) for r in await cursor.fetchall())

    async def get_banned_phrases(self) -> tuple[str, ...]:
        """Return every owner-forbidden phrase ordered by recency."""
        sql = "SELECT phrase FROM banned_phrases ORDER BY created_at DESC"
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql)
            rows = await cursor.fetchall()
        return tuple(str(r[0]) for r in rows)

    async def add_banned_phrase(self, phrase: str, reason: str) -> None:
        """Insert a newly forbidden phrase idempotently."""
        term = phrase.strip()
        if not term:
            return
        now_ms = int(time.time() * 1000)
        sql = "INSERT OR IGNORE INTO banned_phrases (phrase, reason, created_at) VALUES (?, ?, ?)"
        async with self._db.connect() as conn:
            await conn.execute(sql, (term, reason[:120], now_ms))
            await conn.commit()
