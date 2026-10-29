"""Idempotent legacy data-2 migrator and MigrationAuditor for Stage 1 (M1.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import (
    AffectiveVector,
    DriveState,
    EpisodicCard,
    FrozenValueObject,
    ProceduralRule,
    SemanticFact,
    SocialBondProfile,
    WorkingSnapshot,
)

GROUP_CHAT_KEY = "group:10002002"
OWNER_IDS = {"10004004"}
ADMIN_IDS = {"10009010", "10009011"}

AUTHORITATIVE_FACTS: tuple[SemanticFact, ...] = (
    SemanticFact(
        chat_key=GROUP_CHAT_KEY,
        subject="本群真实群主",
        fact_text=(
            "本群唯一真实群主是 kirakiraの馍馍ᕕ(◠ڼ◠)ᕗ (QQ:10004004，外号馍馍/小象)，"
            "形象有两个：直播时是白发蓝瞳小恶魔，群聊时是小白象。"
        ),
        confidence=1.0,
        is_locked=True,
        source="system",
    ),
    SemanticFact(
        chat_key=GROUP_CHAT_KEY,
        subject="本群管理员名单",
        fact_text=(
            "本群真实管理员是 町一(QQ:10009010) 与 JK少女中莫酱(QQ:10009011)。"
            "不要象挑战(10005005)只是普通群员，绝不是群主。"
        ),
        confidence=1.0,
        is_locked=True,
        source="system",
    ),
    SemanticFact(
        chat_key=GROUP_CHAT_KEY,
        subject="回音的主人",
        fact_text="我的唯一主人是 L今晚早睡了吗 (QQ:10001001)，他叫我『回音』或小名『尾尾』。",
        confidence=1.0,
        is_locked=True,
        source="system",
    ),
)

DEFAULT_PROCEDURAL_RULES: tuple[ProceduralRule, ...] = (
    ProceduralRule(
        chat_key=GROUP_CHAT_KEY,
        trigger_keyword="尾尾",
        trigger_user_id="10001001",
        action_instruction="主人L叫我的专属小名『尾尾』时，立即乖巧自然地应声，绝不装傻。",
        strength=10,
    ),
    ProceduralRule(
        chat_key=GROUP_CHAT_KEY,
        trigger_keyword="凤歌",
        trigger_user_id="10008008",
        action_instruction="遇到凤歌储油人(QQ:10008008)冒泡或被提及，可叫他外号『包子头』或向鲸爷请安。",
        strength=8,
    ),
)


class MigrationReport(FrozenValueObject):
    """Immutable audit summary returned after migration."""

    social_bonds_count: int
    episodic_cards_count: int
    semantic_facts_count: int
    procedural_rules_count: int
    stickers_count: int
    plastic_params_count: int


def _read_json_safe(path: Path) -> dict[str, Any] | list[Any]:
    if not path.is_file():
        return {}
    try:
        data: dict[str, Any] | list[Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {}


def _resolve_role(uid: str) -> Literal["owner", "admin", "member"]:
    if uid in OWNER_IDS:
        return "owner"
    if uid in ADMIN_IDS:
        return "admin"
    return "member"


def _parse_card_dict(chat_key: str, item: Any) -> EpisodicCard | None:
    if not isinstance(item, dict):
        return None
    summary = str(item.get("summary", item.get("excerpt", ""))).strip()
    if not summary:
        return None
    raw_parts = item.get("participants", [])
    parts = tuple(str(p.get("name", p.get("id", ""))) for p in raw_parts if isinstance(p, dict))
    ts_val = int(item.get("ts", 0))
    return EpisodicCard(
        chat_key=chat_key,
        timestamp_ms=ts_val,
        msg_seq=int(item.get("msgSeq", 0)),
        summary=summary,
        key_detail=str(item.get("keyDetail", "")),
        participants=parts,
        importance=max(1.0, min(5.0, float(item.get("importance", 3.0)))),
        pinned=bool(item.get("pinned", False)),
        rehearsals=max(0, int(item.get("rehearsals", 0))),
        last_recalled_ms=int(item.get("lastRecalledAt", ts_val)),
    )


def _sticker_to_row(item: Any) -> tuple[Any, ...] | None:
    if not isinstance(item, dict):
        return None
    sid = str(item.get("id", "")).strip()
    if not sid:
        return None
    return (
        sid,
        str(item.get("emojiId", "")),
        str(item.get("md5", "")),
        str(item.get("url", "")),
        str(item.get("localFile", "")),
        str(item.get("desc", "")),
        str(item.get("localNote", "")),
        int(item.get("useCount", 0)),
        int(item.get("lastUsedAt", 0)),
    )


class LegacyDataMigrator:
    """Idempotent migrator importing legacy qq-agent/data-2 into SQLite WAL."""

    def __init__(self, db: SqliteDatabase, legacy_dir: Path) -> None:
        self._db = db
        self._legacy_dir = legacy_dir
        self._mem_repo = SqliteMemoryRepository(db)
        self._work_repo = SqliteWorkingStateStore(db)

    def _load_rivals_map(self) -> dict[str, str]:
        raw = _read_json_safe(self._legacy_dir / "possessive-heart" / "rivals.json")
        rivals = raw.get("rivals", []) if isinstance(raw, dict) else []
        return {
            str(r.get("name", "")): str(r.get("reason", "")) for r in rivals if isinstance(r, dict)
        }

    def _load_profiles_map(self, chat_key: str) -> dict[str, list[str]]:
        fname = f"{chat_key.replace(':', '_')}.json"
        raw = _read_json_safe(self._legacy_dir / "ebbinghaus-memory" / fname)
        profs = raw.get("memberProfiles", {}) if isinstance(raw, dict) else {}
        return {
            str(uid): [str(t) for t in p.get("traits", [])]
            for uid, p in profs.items()
            if isinstance(p, dict)
        }

    async def _migrate_social_bonds(self) -> int:
        aff = _read_json_safe(self._legacy_dir / "affinity.json")
        chats = aff.get("chats", {}) if isinstance(aff, dict) else {}
        rivals_map = self._load_rivals_map()
        count = 0
        for chat_key, chat_obj in chats.items():
            if not isinstance(chat_obj, dict):
                continue
            traits = self._load_profiles_map(str(chat_key))
            count += await self._upsert_chat_members(
                str(chat_key), chat_obj.get("members", {}), traits, rivals_map
            )
        return count

    async def _upsert_chat_members(
        self,
        chat_key: str,
        members: dict[str, Any],
        traits_by_uid: dict[str, list[str]],
        rivals_map: dict[str, str],
    ) -> int:
        written = 0
        for uid, rec in members.items():
            if not isinstance(rec, dict):
                continue
            name = str(rec.get("name", uid))
            trust = 1.0 if uid == "10001001" else (0.55 if uid == "10005005" else 0.80)
            bond = SocialBondProfile(
                chat_key=chat_key,
                user_id=str(uid),
                user_name=name,
                group_role=_resolve_role(str(uid)),
                affinity_score=float(rec.get("score", 0.0)),
                affinity_level=max(0, min(5, int(rec.get("level", 1)))),
                msg_count=int(rec.get("msgs", 0)),
                trust_score=trust,
                is_rival=(name in rivals_map and bool(name)),
                rival_reason=rivals_map.get(name, ""),
                traits=tuple(traits_by_uid.get(str(uid), [])),
            )
            await self._mem_repo.upsert_social_bond(bond)
            written += 1
        return written

    def _cards_from_file(self, fpath: Path) -> list[EpisodicCard]:
        raw = _read_json_safe(fpath)
        if not isinstance(raw, dict):
            return []
        ck = str(raw.get("chatKey", fpath.stem.replace("_", ":", 1)))
        parsed = [_parse_card_dict(ck, it) for it in raw.get("items", [])]
        return [c for c in parsed if c is not None]

    def _scan_episodic_files(self) -> list[EpisodicCard]:
        ebb_dir = self._legacy_dir / "ebbinghaus-memory"
        if not ebb_dir.is_dir():
            return []
        return [c for f in sorted(ebb_dir.glob("*.json")) for c in self._cards_from_file(f)]

    async def _migrate_episodic_cards(self) -> int:
        cards = self._scan_episodic_files()
        async with self._db.connect() as conn:
            cursor = await conn.execute("SELECT chat_key, summary FROM episodic_memories")
            existing = {(str(r[0]), str(r[1])) for r in await cursor.fetchall()}
        for card in cards:
            key = (card.chat_key, card.summary)
            if key not in existing:
                await self._mem_repo.save_episodic_card(card)
                existing.add(key)
        return len(existing)

    async def _migrate_working_and_stickers(self) -> int:
        hl = _read_json_safe(self._legacy_dir / "her-life.json")
        ph = _read_json_safe(self._legacy_dir / "possessive-heart.json")
        hl_dict = hl if isinstance(hl, dict) else {}
        ph_dict = ph if isinstance(ph, dict) else {}
        desire = float(ph_dict.get("desire", 80.0))
        jealousy = float(ph_dict.get("jealousy", 0.0))
        snap = WorkingSnapshot(
            scope_key="global",
            affect=AffectiveVector(valence=35.0, energy=85.0, jealousy=jealousy, shyness=15.0),
            drives=DriveState(
                curiosity=60.0,
                attachment=max(0.0, min(100.0, desire)),
                jealousy_drive=jealousy,
                social_expression=55.0,
            ),
            current_activity=str(hl_dict.get("currentActivity", "正窝着织一条蓝色围巾")),
            inner_thought=str(hl_dict.get("lastThought", "")),
        )
        await self._work_repo.save_working_state(snap)
        pg = _read_json_safe(self._legacy_dir / "persona-grow" / "state.json")
        elems = pg.get("elements", []) if isinstance(pg, dict) else []
        async with self._db.connect() as conn:
            for el in elems:
                if isinstance(el, dict) and el.get("text"):
                    await conn.execute(
                        "INSERT OR IGNORE INTO persona_traits (category, trait_text, strength, created_at) VALUES (?, ?, ?, ?)",
                        ("habit", str(el["text"]), 5, int(el.get("addedAt", 0))),
                    )
            await conn.commit()
        return await self._import_stickers()

    async def _import_stickers(self) -> int:
        raw = _read_json_safe(self._legacy_dir / "stickers.json")
        items = raw if isinstance(raw, list) else []
        rows = [r for r in (_sticker_to_row(item) for item in items) if r is not None]
        sql = (
            "INSERT OR REPLACE INTO stickers "
            "(id, emoji_id, md5, url, local_file, desc_text, local_note, use_count, last_used_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        async with self._db.connect() as conn:
            await conn.executemany(sql, rows)
            await conn.commit()
        return len(rows)

    async def run(self) -> MigrationReport:
        """Execute full idempotent migration and return audit counts."""
        await self._db.initialize()
        await self._work_repo.ensure_default_params()
        bonds_n = await self._migrate_social_bonds()
        cards_n = await self._migrate_episodic_cards()
        for fact in AUTHORITATIVE_FACTS:
            await self._mem_repo.upsert_semantic_fact(fact)
        for rule in DEFAULT_PROCEDURAL_RULES:
            await self._mem_repo.upsert_procedural_rule(rule)
        stickers_n = await self._migrate_working_and_stickers()
        params = await self._work_repo.get_plastic_params()
        facts = await self._mem_repo.get_semantic_facts(GROUP_CHAT_KEY)
        rules = await self._mem_repo.get_procedural_rules(GROUP_CHAT_KEY)
        return MigrationReport(
            social_bonds_count=bonds_n,
            episodic_cards_count=cards_n,
            semantic_facts_count=len(facts),
            procedural_rules_count=len(rules),
            stickers_count=stickers_n,
            plastic_params_count=len(params),
        )


async def _cli_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Migrate legacy qq-agent data into EchoMind DB")
    parser.add_argument(
        "--legacy-dir",
        type=Path,
        default=Path("/home/polyisoprene/Documents/qq-agent/data-2"),
    )
    parser.add_argument("--target-db", type=Path, default=Path("data/echomind.db"))
    args = parser.parse_args()
    db = SqliteDatabase(args.target_db)
    report = await LegacyDataMigrator(db, args.legacy_dir).run()
    print("✅ Migration completed:")
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(_cli_main())
