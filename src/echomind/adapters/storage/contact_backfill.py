"""Stage 40: backfill social bonds from the message history (historical speakers)."""

from __future__ import annotations

from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.domain.models import Percept, SocialBondProfile

_SQL = (
    "SELECT chat_key, sender_id, COUNT(*), MAX(ts) FROM chat_messages "
    "WHERE is_self = 0"
)
_SQL_NAME = (
    "SELECT sender_name FROM chat_messages WHERE chat_key = ? AND sender_id = ? "
    "AND is_self = 0 ORDER BY ts DESC LIMIT 1"
)


def _new_bond(chat_key: str, uid: str, name: str, count: int, last_ms: int) -> SocialBondProfile:
    percept = Percept(chat_key=chat_key, scene="group", message_id="", timestamp_ms=last_ms,
                      sender_id=uid, sender_name=name, text="")
    from echomind.mind.memory_consolidator import _default_bond

    bond = _default_bond(chat_key, percept, False)
    return bond.model_copy(update={"msg_count": count, "last_seen_ms": last_ms})


async def backfill_contacts(db: SqliteDatabase, chat_key: str = "") -> dict[str, Any]:
    """Create missing bonds and refresh counts from chat history (idempotent)."""
    repo = SqliteMemoryRepository(db)
    sql, params = (_SQL + " AND chat_key = ? GROUP BY 1, 2", (chat_key,)) if chat_key \
        else (_SQL + " GROUP BY 1, 2", ())
    async with db.connect() as conn:
        rows = list(await (await conn.execute(sql, params)).fetchall())
        names: dict[tuple[str, str], str] = {}
        for ck, uid, _count, _last in rows:
            cur = await conn.execute(_SQL_NAME, (ck, uid))
            name_row = await cur.fetchone()
            names[(str(ck), str(uid))] = str(name_row[0]) if name_row else str(uid)

    created = updated = 0
    for ck, uid, count, last_ms in rows:
        ck, uid = str(ck), str(uid)
        bond = await repo.get_social_bond(ck, uid)
        if bond is None:
            await repo.upsert_social_bond(
                _new_bond(ck, uid, names[(ck, uid)], int(count), int(last_ms))
            )
            created += 1
            continue
        await repo.upsert_social_bond(bond.model_copy(update={
            "msg_count": max(bond.msg_count, int(count)),
            "last_seen_ms": max(bond.last_seen_ms, int(last_ms)),
            "user_name": bond.user_name or names[(ck, uid)],
        }))
        updated += 1
    return {"senders": len(rows), "created": created, "updated": updated}
