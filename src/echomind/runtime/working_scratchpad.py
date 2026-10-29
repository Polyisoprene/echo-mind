"""M19.3 Cross-Turn Working Scratchpad & Continuity Buffer (MemGPT-Inspired)."""

from __future__ import annotations

import datetime

CST = datetime.timezone(datetime.timedelta(hours=8))
SCRATCHPAD_TTL_MS = 20 * 60_000
INVESTIGATIVE_TOOLS = frozenset(
    {
        "get_group_members",
        "web_search",
        "meme_wiki",
        "bili_search",
        "bili_video",
        "bili_popular",
        "look_at_image",
        "watch_video",
        "read_voice",
        "read_forward",
        "recall_memory",
    }
)


def _fmt_hhmm(ts_ms: int) -> str:
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=CST)
    return dt.strftime("%H:%M")


class WorkingScratchpad:
    """Maintain a 20-minute rolling buffer of tool findings & self-replies per chat."""

    def __init__(self) -> None:
        self._notes: dict[str, list[tuple[int, str]]] = {}

    def _prune_expired(self, chat_key: str, now_ms: int) -> list[tuple[int, str]]:
        items = self._notes.get(chat_key, [])
        fresh = [(ts, line) for ts, line in items if (now_ms - ts) <= SCRATCHPAD_TTL_MS]
        self._notes[chat_key] = fresh[-6:]
        return self._notes[chat_key]

    def record_tool_finding(
        self, chat_key: str, tool_name: str, result_str: str, now_ms: int
    ) -> None:
        """Cache key output from an investigative tool for subsequent turns."""
        if tool_name not in INVESTIGATIVE_TOOLS:
            return
        clean = " ".join(result_str.strip().splitlines())[:220]
        if not clean or clean.startswith("工具 "):
            return
        entry = f"- [{_fmt_hhmm(now_ms)} 刚查过 {tool_name}]: {clean}"
        notes = self._prune_expired(chat_key, now_ms)
        notes.append((now_ms, entry))
        self._notes[chat_key] = notes[-6:]

    def record_self_reply(
        self, chat_key: str, sent_texts: tuple[str, ...], now_ms: int
    ) -> None:
        """Record the agent's own spoken utterance so the next turn keeps continuity."""
        if not sent_texts:
            return
        joined = " / ".join(sent_texts)[:140]
        entry = f"- [{_fmt_hhmm(now_ms)} 我上一轮刚说]: {joined}"
        notes = self._prune_expired(chat_key, now_ms)
        notes.append((now_ms, entry))
        self._notes[chat_key] = notes[-6:]

    def render_continuity_block(self, chat_key: str, now_ms: int) -> str:
        """Render the non-expired working scratchpad block for prompt injection."""
        notes = self._prune_expired(chat_key, now_ms)
        if not notes:
            return ""
        header = "【🧩 跨轮次工作记忆延续（你刚才查到的资料与上轮话锋，切勿转头失忆）】"
        return header + "\n" + "\n".join(line for _, line in notes)
