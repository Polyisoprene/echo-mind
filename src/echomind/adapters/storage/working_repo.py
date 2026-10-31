"""SQLite implementation of IWorkingStateStore with 7D HEXACO personality & homeostatic bounds."""

from __future__ import annotations

import json
import time
from typing import Any, Literal, cast

import aiosqlite

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.working_writer import save_snapshot
from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    IntentionItem,
    PersonaTrait,
    PlasticParamSpec,
    WorkingSnapshot,
)
from echomind.domain.persona_specs import PERSONA_SPECS


async def _decay_traits(conn: Any, delta: int, categories: tuple[str, ...]) -> None:
    """Apply a negative shift globally, or only to the given categories when specified."""
    if not categories:
        await conn.execute(
            "UPDATE persona_traits SET strength = MAX(0, strength + ?)", (delta,)
        )
        return
    for category in categories:
        await conn.execute(
            "UPDATE persona_traits SET strength = MAX(0, strength + ?) WHERE category = ?",
            (delta, category),
        )


async def _cap_trait_categories(conn: Any) -> None:
    """Keep only the strongest traits per category (habit 8 / taste 4 / temperament 4 / taboo 3)."""
    for category, cap in _TRAIT_CAPS.items():
        await conn.execute(
            "DELETE FROM persona_traits WHERE category = ? AND id NOT IN ("
            "SELECT id FROM persona_traits WHERE category = ? "
            "ORDER BY strength DESC, created_at DESC LIMIT ?)",
            (category, category, cap),
        )


_TRAIT_CAPS: dict[str, int] = {
    "habit": 8, "taste": 4, "temperament": 4, "taboo": 3,
}

TraitCategory = Literal["habit", "temperament", "taste", "taboo"]


def _spec(key: str, val: float, lo: float, hi: float, desc: str) -> PlasticParamSpec:
    return PlasticParamSpec(key=key, value=val, min_bound=lo, max_bound=hi, description=desc)


DEFAULT_PLASTIC_PARAMS: tuple[PlasticParamSpec, ...] = (
    _spec("talkativeness", 58.0, 20.0, 90.0, "群聊插话积极度"),
    _spec("proactive_idle_min", 10.0, 5.0, 30.0, "冷场主动开口等待分钟数"),
    _spec("skepticism", 55.0, 10.0, 95.0, "元认知防忽悠怀疑警觉度"),
    _spec("verify_impulse", 70.0, 20.0, 95.0, "遇到可疑断言主动调工具核验冲动"),
    _spec("curiosity_rate", 65.0, 20.0, 95.0, "好奇心增长率与主动搜索欲"),
    *(
        _spec(spec.key, spec.default, spec.min_bound, spec.max_bound, spec.description)
        for spec in PERSONA_SPECS.values()
    ),
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
        revision=int(row[13]),
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
            "intentions_json, curiosity_queue_json, updated_at "
            "FROM working_state WHERE scope_key = ?"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (scope_key,))
            return _row_to_snapshot(scope_key, await cursor.fetchone())

    async def save_working_state(self, snapshot: WorkingSnapshot) -> None:
        await save_snapshot(self._db, snapshot)

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

    async def persona_day_usage(self, key: str, since_ms: int) -> float:
        """Absolute change already applied to one persona dimension since `since_ms`."""
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(ABS(new_val - old_val)), 0) FROM plastic_logs "
                "WHERE param_key = ? AND ts >= ?",
                (key, since_ms),
            )
            row = await cursor.fetchone()
        return float(row[0]) if row else 0.0

    async def persona_last_update_ms(self, key: str) -> int:
        """Timestamp of the most recent change to one persona dimension (0 if never)."""
        async with self._db.connect() as conn:
            cursor = await conn.execute(
                "SELECT COALESCE(MAX(ts), 0) FROM plastic_logs WHERE param_key = ?", (key,)
            )
            row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def sync_persona_traits(
        self, new_trait: PersonaTrait | None = None, strength_delta: int = 0,
        *, chat_key: str = "", source: str = "",
        decay_categories: tuple[str, ...] = (),
    ) -> tuple[PersonaTrait, ...]:
        now_ms = int(time.time() * 1000)
        stale_cutoff = now_ms - 43_200_000  # 12h without reinforcement triggers decay
        async with self._db.connect() as conn:
            if strength_delta < 0:
                await _decay_traits(conn, strength_delta, decay_categories)
            await conn.execute(
                "UPDATE persona_traits SET strength = strength - 1, created_at = ? "
                "WHERE created_at > 0 AND created_at < ?",
                (now_ms, stale_cutoff),
            )
            await conn.execute("DELETE FROM persona_traits WHERE strength <= 0")
            if new_trait and new_trait.trait_text.strip():
                await conn.execute(
                    "INSERT INTO persona_traits (category, trait_text, strength, created_at, "
                    "chat_key, source) VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(trait_text) DO UPDATE SET "
                    "strength = MIN(10, persona_traits.strength + 2), "
                    "created_at = excluded.created_at, chat_key = excluded.chat_key, "
                    "source = excluded.source",
                    (new_trait.category, new_trait.trait_text.strip(), new_trait.strength,
                     now_ms, chat_key, source),
                )
            await _cap_trait_categories(conn)
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
