"""M4.1 Holy Web Search (anti-derailment) & Feiyu Voice/Song-Cover Tools."""

from __future__ import annotations

import re
from typing import Any, Protocol

from echomind.domain.ports import IBiliClient

MEME_TAIL_RE = re.compile(r"(?:是什么梗|是什么意思|是什么|是谁呀|是谁|怎么回事|有什么含义)+$")
HTML_TAG_STRIP_RE = re.compile(r"<[^>]+>")


class ISearchBackend(Protocol):
    """Abstract search backend protocol for DIP & deterministic unit testing."""

    async def fetch_snippets(self, query: str) -> tuple[str, ...]: ...


class BiliSearchBackend:
    """ISearchBackend adapter querying Bilibili videos for real-time topics & memes."""

    def __init__(self, bili: IBiliClient) -> None:
        self._bili = bili

    async def fetch_snippets(self, query: str) -> tuple[str, ...]:
        try:
            items = await self._bili.search_videos(query, limit=4)
        except Exception:
            return ()
        out: list[str] = []
        for it in items:
            title = HTML_TAG_STRIP_RE.sub("", str(it.get("title", ""))).strip()
            author = str(it.get("author", "")).strip()
            bvid = str(it.get("bvid", "")).strip()
            desc = str(it.get("description", "")).strip()[:80]
            url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""
            if title:
                out.append(f"- [B站视频] 《{title}》｜UP主:{author}｜{url} {desc}".strip())
        return tuple(out)


def clean_meme_query(raw_query: str) -> str:
    """Strip conversational question tails so search engines don't degrade to single-char lookup."""
    stripped = MEME_TAIL_RE.sub("", raw_query.strip().rstrip(" ？?！!。.")).strip()
    return stripped if stripped else raw_query.strip()


class CompositeSearchBackend:
    """Composite pattern chaining multiple ISearchBackend sources with fault isolation."""

    def __init__(self, backends: tuple[ISearchBackend, ...]) -> None:
        self._backends = backends

    async def fetch_snippets(self, query: str) -> tuple[str, ...]:
        merged: list[str] = []
        for backend in self._backends:
            try:
                res = await backend.fetch_snippets(query)
            except Exception:
                res = ()
            merged.extend(s for s in res if s and s not in merged)
        return tuple(merged)


class HolyWebSearchTool:
    """Epistemic web search tool with Chinese meme tail stripping & Moegirl priority."""

    category = "信息探索"

    def __init__(self, backend: ISearchBackend) -> None:
        self._backend = backend

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "联网搜索未知的新词、热梗、动漫游戏设定或实时资讯（支持好奇心主动求知）。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

    async def execute(self, _chat_key: str, args: dict[str, Any]) -> str:
        raw_q = str(args.get("query", "")).strip()
        if not raw_q:
            return "搜索词为空"
        clean_q = clean_meme_query(raw_q)
        snippets = await self._backend.fetch_snippets(clean_q)
        if not snippets:
            return f"未搜到关于『{clean_q}』的有效结果。"
        joined = "\n".join(f"- {s}" for s in snippets[:5])
        return f"🔍 搜索『{clean_q}』结果：\n{joined}"
