"""M4.1 CNMeme Wiki (https://cnmeme.wiki) Client & Tool with ETag Cache & HTML Sanitizer."""

from __future__ import annotations

import html
import re
import time
from typing import Any, Protocol
from urllib.parse import quote, urlencode

import httpx

from echomind.domain.models import FrozenValueObject
from echomind.tools.explore_and_voice import clean_meme_query

CNMEME_BASE_URL = "https://cnmeme.wiki"
HTML_TAG_RE = re.compile(r"<[^>]+>")
MULTI_SPACE_RE = re.compile(r"\s+")


class MemeWikiEntry(FrozenValueObject):
    """Immutable structured meme entry from cnmeme.wiki API v1."""

    slug: str
    title: str
    summary: str
    content_text: str = ""
    tags: tuple[str, ...] = ()
    bvid: str = ""
    video_title: str = ""


class IHttpGetJsonTransport(Protocol):
    """Abstract HTTP GET transport supporting ETag / 304 conditional requests (DIP & LSP)."""

    async def get_json_with_etag(
        self, url: str, if_none_match: str = "", timeout_s: float = 10.0
    ) -> tuple[int, dict[str, Any], str]: ...


class HttpxGetJsonTransport:
    """Production httpx implementation of IHttpGetJsonTransport."""

    async def get_json_with_etag(
        self, url: str, if_none_match: str = "", timeout_s: float = 5.0
    ) -> tuple[int, dict[str, Any], str]:
        headers = {"Accept": "application/json"}
        if if_none_match:
            headers["If-None-Match"] = if_none_match
        async with httpx.AsyncClient(timeout=timeout_s, trust_env=False) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 304:
                return 304, {}, if_none_match
            if resp.status_code == 404:
                return 404, {}, ""
            resp.raise_for_status()
            etag = str(resp.headers.get("ETag", ""))
            data: dict[str, Any] = resp.json()
            return 200, data, etag


def html_to_clean_text(raw_html: str) -> str:
    """Strip whitelisted HTML tags from cnmeme.wiki content_html into clean plain text."""
    if not raw_html:
        return ""
    spaced = re.sub(r"</(?:p|h[1-6]|li|blockquote)>", "\n", raw_html)
    no_tags = HTML_TAG_RE.sub("", spaced)
    unescaped = html.unescape(no_tags)
    lines = [MULTI_SPACE_RE.sub(" ", ln).strip() for ln in unescaped.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _item_to_entry(item: dict[str, Any], detail_html: str = "") -> MemeWikiEntry:
    raw_tags = item.get("tags", [])
    tags = tuple(str(t) for t in raw_tags if str(t)) if isinstance(raw_tags, list) else ()
    sv = item.get("source_video")
    bvid = str(sv.get("bvid", "")) if isinstance(sv, dict) else ""
    v_title = str(sv.get("title", "")) if isinstance(sv, dict) else ""
    return MemeWikiEntry(
        slug=str(item.get("slug", "")),
        title=str(item.get("title", "")),
        summary=str(item.get("summary", "")),
        content_text=html_to_clean_text(detail_html)[:500],
        tags=tags,
        bvid=bvid,
        video_title=v_title,
    )


def format_meme_entry(entry: MemeWikiEntry) -> str:
    """Format a MemeWikiEntry into a high-density readable snippet for the agent."""
    tag_str = f" [标签: {', '.join(entry.tags[:5])}]" if entry.tags else ""
    body = entry.content_text if entry.content_text else entry.summary
    vid_str = (
        f" (来源视频: {entry.video_title} https://www.bilibili.com/video/{entry.bvid})"
        if entry.bvid
        else ""
    )
    return f"【梗Wiki · {entry.title}】{tag_str}\n{body}{vid_str}"


class CnMemeWikiClient:
    """Client for https://cnmeme.wiki/api/v1/public/memes with TTL + ETag caching."""

    def __init__(self, transport: IHttpGetJsonTransport | None = None) -> None:
        self._transport: IHttpGetJsonTransport = (
            transport if transport is not None else HttpxGetJsonTransport()
        )
        self._cache: dict[str, tuple[float, str, dict[str, Any]]] = {}

    async def _fetch_cached(self, path: str, ttl_sec: float) -> dict[str, Any]:
        now = time.monotonic()
        cached = self._cache.get(path)
        if cached and (now - cached[0]) < ttl_sec:
            return cached[2]
        prev_etag = cached[1] if cached else ""
        status, data, new_etag = await self._transport.get_json_with_etag(
            f"{CNMEME_BASE_URL}{path}", if_none_match=prev_etag
        )
        if status == 304 and cached:
            self._cache[path] = (now, cached[1], cached[2])
            return cached[2]
        if status == 200 and data:
            self._cache[path] = (now, new_etag, data)
            return data
        return {}

    async def get_detail_html(self, slug: str) -> str:
        if not slug:
            return ""
        encoded = quote(slug, safe="")
        data = await self._fetch_cached(f"/api/v1/public/memes/{encoded}", ttl_sec=120.0)
        item = data.get("item", {})
        return str(item.get("content_html", "")) if isinstance(item, dict) else ""

    async def search_memes(
        self, query: str = "", tag: str = "", limit: int = 3
    ) -> tuple[MemeWikiEntry, ...]:
        clean_q = clean_meme_query(query) if query else ""
        clamped_limit = max(1, min(10, limit))
        qs = urlencode({"q": clean_q[:80], "tag": tag[:40], "limit": clamped_limit})
        page = await self._fetch_cached(f"/api/v1/public/memes?{qs}", ttl_sec=60.0)
        raw_items = page.get("items", [])
        if not isinstance(raw_items, list) or not raw_items:
            return ()
        entries: list[MemeWikiEntry] = []
        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            detail_html = await self.get_detail_html(str(item.get("slug", ""))) if idx == 0 else ""
            entries.append(_item_to_entry(item, detail_html))
        return tuple(entries)

    async def fetch_snippets(self, query: str) -> tuple[str, ...]:
        """Satisfy ISearchBackend protocol so CnMemeWikiClient plugs into HolyWebSearchTool!"""
        entries = await self.search_memes(query=query, limit=3)
        return tuple(format_meme_entry(e) for e in entries)


class CnMemeWikiTool:
    """Dedicated IToolExtension for searching or browsing latest memes on cnmeme.wiki."""

    category = "信息探索"

    def __init__(self, client: CnMemeWikiClient) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "meme_wiki"

    @property
    def description(self) -> str:
        return (
            "查询『梗Wiki (cnmeme.wiki)』最新网络热梗词典：传入 query 查特定梗的起源与B站出处；"
            "query 留空则浏览最新收录的热门新梗（适合闲暇冲浪学新梗）。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "tag": {"type": "string"},
                "limit": {"type": "integer"},
            },
        }

    async def execute(self, _chat_key: str, args: dict[str, Any]) -> str:
        q = str(args.get("query", "")).strip()
        tag = str(args.get("tag", "")).strip()
        limit = int(args.get("limit", 3))
        entries = await self._client.search_memes(query=q, tag=tag, limit=limit)
        if not entries:
            return f"梗Wiki 中暂未收录『{q or tag}』相关词条，可尝试调用 web_search 搜索全网。"
        return "\n\n".join(format_meme_entry(e) for e in entries)
