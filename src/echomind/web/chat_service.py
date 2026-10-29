"""Session list, message stream, log tail, sticker library and usage statistics."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer

MAX_LOG_LINES = 400


def _msg_row(row: Any) -> dict[str, Any]:
    return {
        "id": int(row[0]),
        "ts": int(row[1]),
        "sender_id": str(row[2]),
        "sender_name": str(row[3]),
        "is_self": bool(row[4]),
        "text": str(row[5]),
    }


class ChatStreamService:
    """Backing service for the session, message, log and usage panels."""

    def __init__(self, container: EchoMindContainer, log_path: Path) -> None:
        self._c = container
        self._log_path = log_path

    async def list_sessions(self) -> list[dict[str, Any]]:
        """Return every chat key with aggregate counters and its latest message."""
        agg_sql = (
            "SELECT chat_key, COUNT(*) AS total, MAX(ts) AS last_ts, "
            "SUM(CASE WHEN is_self = 0 THEN 1 ELSE 0 END) AS peer_msgs "
            "FROM chat_messages GROUP BY chat_key ORDER BY last_ts DESC LIMIT 60"
        )
        last_sql = (
            "SELECT m.chat_key, m.text, m.sender_name, m.is_self FROM chat_messages m "
            "JOIN (SELECT chat_key, MAX(id) AS mx FROM chat_messages GROUP BY chat_key) t "
            "ON m.chat_key = t.chat_key AND m.id = t.mx"
        )
        async with self._c.db.connect() as conn:
            cursor = await conn.execute(agg_sql)
            agg_rows = list(await cursor.fetchall())
            cursor2 = await conn.execute(last_sql)
            last_map = {
                str(r[0]): (str(r[1]), str(r[2]), bool(r[3])) for r in await cursor2.fetchall()
            }
        sessions: list[dict[str, Any]] = []
        for row in agg_rows:
            key = str(row[0])
            preview, who, _ = last_map.get(key, ("", "", False))
            sessions.append(
                {
                    "chat_key": key,
                    "total": int(row[1]),
                    "last_ts": int(row[2]),
                    "peer_msgs": int(row[3] or 0),
                    "preview": preview[:60],
                    "last_sender": who,
                }
            )
        return sessions

    async def list_messages(self, chat_key: str, limit: int = 120) -> list[dict[str, Any]]:
        """Return the newest messages of one chat in chronological order."""
        sql = (
            "SELECT id, ts, sender_id, sender_name, is_self, text FROM chat_messages "
            "WHERE chat_key = ? ORDER BY id DESC LIMIT ?"
        )
        async with self._c.db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key, max(1, min(limit, 300))))
            rows = list(await cursor.fetchall())
        return [_msg_row(r) for r in reversed(rows)]

    async def list_stickers(self, limit: int = 60) -> list[dict[str, Any]]:
        """Return the sticker library ordered by usage."""
        sql = (
            "SELECT id, desc_text, local_note, use_count, last_used_at FROM stickers "
            "ORDER BY use_count DESC, id ASC LIMIT ?"
        )
        async with self._c.db.connect() as conn:
            cursor = await conn.execute(sql, (limit,))
            rows = list(await cursor.fetchall())
        return [
            {
                "id": str(r[0]),
                "desc": str(r[1] or ""),
                "note": str(r[2] or ""),
                "use_count": int(r[3] or 0),
                "last_used_at": int(r[4] or 0),
            }
            for r in rows
        ]

    async def usage_stats(self) -> dict[str, Any]:
        """Aggregate LLM call volume, latency and token consumption since Beijing 00:00."""
        day_start = ((int(time.time()) + 28800) // 86400 * 86400 - 28800) * 1000
        sql = (
            "SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(cached_tokens),0), "
            "COALESCE(SUM(completion_tokens),0), COALESCE(AVG(elapsed_ms),0), "
            "COALESCE(SUM(is_failover),0) FROM llm_traces WHERE ts >= ?"
        )
        async with self._c.db.connect() as conn:
            cursor = await conn.execute(sql, (day_start,))
            row = await cursor.fetchone()
        if row is None:
            return {
                "calls": 0,
                "prompt": 0,
                "cached": 0,
                "completion": 0,
                "avg_ms": 0.0,
                "failover": 0,
            }
        return {
            "calls": int(row[0]),
            "prompt": int(row[1]),
            "cached": int(row[2]),
            "completion": int(row[3]),
            "avg_ms": round(float(row[4]), 1),
            "failover": int(row[5]),
        }

    async def tail_logs(self, lines: int = 120) -> list[str]:
        """Return the newest console log lines (bounded)."""
        count = max(10, min(lines, MAX_LOG_LINES))
        if not self._log_path.is_file():
            return []
        text = self._log_path.read_text(encoding="utf-8", errors="replace")
        return text.splitlines()[-count:]

    async def list_llm_traces(self, limit: int = 60) -> list[dict[str, Any]]:
        """Return the newest per-request LLM traces, newest first."""
        sql = (
            "SELECT ts, chat_key, gateway_name, model_name, elapsed_ms, "
            "prompt_tokens, cached_tokens, completion_tokens, is_failover "
            "FROM llm_traces ORDER BY id DESC LIMIT ?"
        )
        async with self._c.db.connect() as conn:
            cursor = await conn.execute(sql, (max(1, min(limit, 300)),))
            rows = await cursor.fetchall()
        return [
            {
                "ts": int(r[0]),
                "chat_key": str(r[1] or ""),
                "gateway": str(r[2]),
                "model": str(r[3]),
                "elapsed_ms": int(r[4]),
                "prompt": int(r[5]),
                "cached": int(r[6]),
                "completion": int(r[7]),
                "failover": bool(r[8]),
            }
            for r in rows
        ]

    async def list_turns(self, chat_key: str = "", limit: int = 40) -> list[dict[str, Any]]:
        """Return per-turn execution timelines, newest first."""
        records = await self._c.trace_store.list_turns(chat_key, limit)
        return [
            {
                "turn_id": r.turn_id,
                "chat_key": r.chat_key,
                "ts": r.ts,
                "trigger": r.trigger,
                "status": r.status,
                "rounds": r.rounds,
                "sent_count": r.sent_count,
                "total_ms": r.total_ms,
                "model": r.model,
                "context_count": r.context_count,
                "trigger_count": r.trigger_count,
                "system_prompt": r.system_prompt,
                "user_prompt": r.user_prompt,
                "steps": [s.model_dump() for s in r.steps],
            }
            for r in records
        ]
