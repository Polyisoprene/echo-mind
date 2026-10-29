"""Bilibili read-only client: WBI signing, cookie auth, search and video metadata."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any
from urllib.parse import urlencode

import httpx

BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
HTML_EM_RE = re.compile(r"<[^>]+>")

API = "https://api.bilibili.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT_S = 12.0
HEADERS = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]


WBI_TTL_S = 3600.0


def mixin_key(orig: str) -> str:
    """Derive the WBI mixin key from img_key + sub_key with length guard."""
    if len(orig) < 64:
        return orig.ljust(32, "0")[:32]
    return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign_params(params: dict[str, Any], img_key: str, sub_key: str, ts: int | None = None) -> str:
    """Return a WBI-signed query string."""
    key = mixin_key(img_key + sub_key)
    payload = dict(params)
    payload["wts"] = int(ts if ts is not None else time.time())
    ordered = dict(sorted(payload.items()))
    query = urlencode({k: str(v) for k, v in ordered.items()})
    payload["w_rid"] = hashlib.md5((query + key).encode(), usedforsecurity=False).hexdigest()
    return urlencode({k: str(v) for k, v in sorted(payload.items())})


def build_cookie(sessdata: str = "", bili_jct: str = "", dede_user_id: str = "") -> str:
    """Assemble a Cookie header from the three fields B站 needs."""
    parts = []
    if sessdata:
        parts.append(f"SESSDATA={sessdata}")
    if bili_jct:
        parts.append(f"bili_jct={bili_jct}")
    if dede_user_id:
        parts.append(f"DedeUserID={dede_user_id}")
    return "; ".join(parts)


def _extract_stream_url(body: dict[str, Any]) -> str:
    data = body.get("data")
    if not isinstance(data, dict):
        return ""
    dash = data.get("dash")
    audios = dash.get("audio") if isinstance(dash, dict) else None
    if isinstance(audios, list) and audios and isinstance(audios[0], dict):
        return str(audios[0].get("baseUrl", audios[0].get("base_url", "")))
    durl = data.get("durl")
    if isinstance(durl, list) and durl and isinstance(durl[0], dict):
        return str(durl[0].get("url", ""))
    return ""


class BiliClient:
    """Minimal B站 client used by the bili_* skills."""

    def __init__(self, cookie_provider: Any = None) -> None:
        self._cookie_provider = cookie_provider
        self._wbi_keys: tuple[str, str] | None = None
        self._wbi_ts: float = 0.0

    async def _cookie(self) -> str:
        if self._cookie_provider is None:
            return ""
        values = await self._cookie_provider()
        return build_cookie(
            values.get("sessdata", ""), values.get("bili_jct", ""), values.get("dedeuserid", "")
        )

    async def _headers(self) -> dict[str, str]:
        headers = dict(HEADERS)
        cookie = await self._cookie()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    async def _get_json(self, url: str) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_S, trust_env=False, follow_redirects=True
        ) as c:
            resp = await c.get(url, headers=await self._headers())
            resp.raise_for_status()
            body = resp.json()
        return body if isinstance(body, dict) else {}

    async def _keys(self) -> tuple[str, str]:
        now = time.monotonic()
        if self._wbi_keys is not None and (now - self._wbi_ts) < WBI_TTL_S:
            return self._wbi_keys
        body = await self._get_json(f"{API}/x/web-interface/nav")
        wbi = body.get("data", {}).get("wbi_img", {}) if isinstance(body.get("data"), dict) else {}
        img = str(wbi.get("img_url", "")).rsplit("/", 1)[-1].split(".")[0]
        sub = str(wbi.get("sub_url", "")).rsplit("/", 1)[-1].split(".")[0]
        if len(img) + len(sub) >= 64:
            self._wbi_keys = (img, sub)
            self._wbi_ts = now
        return (img, sub)

    async def search_videos(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search videos by keyword (requires WBI signature)."""
        img, sub = await self._keys()
        query = sign_params(
            {"search_type": "video", "keyword": keyword, "page": 1, "page_size": limit}, img, sub
        )
        body = await self._get_json(f"{API}/x/web-interface/wbi/search/type?{query}")
        items = body.get("data", {}).get("result") if isinstance(body.get("data"), dict) else None
        return [i for i in (items or []) if isinstance(i, dict)][:limit]

    async def video_info(self, bvid: str) -> dict[str, Any]:
        """Fetch one video's metadata by BV id."""
        body = await self._get_json(f"{API}/x/web-interface/view?bvid={bvid}")
        data = body.get("data")
        return data if isinstance(data, dict) else {}

    async def popular(self, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch the popular list."""
        body = await self._get_json(f"{API}/x/web-interface/popular?ps={limit}&pn=1")
        items = body.get("data", {}).get("list") if isinstance(body.get("data"), dict) else None
        return [i for i in (items or []) if isinstance(i, dict)][:limit]

    async def _resolve_song_bvid(self, query: str) -> tuple[str, str]:
        m = BV_RE.search(query)
        if m:
            return m.group(1), query
        items = await self.search_videos(f"{query} 原版 音乐", limit=5)
        for item in items:
            bvid = str(item.get("bvid") or "").strip()
            if bvid:
                title = HTML_EM_RE.sub("", str(item.get("title") or query)).strip()
                return bvid, title
        raise RuntimeError(f"在B站未搜到歌曲『{query}』的音源")

    async def _fetch_audio_stream_url(self, bvid: str, cid: int) -> str:
        img, sub = await self._keys()
        q = sign_params({"bvid": bvid, "cid": cid, "fnval": 16}, img, sub)
        body = await self._get_json(f"{API}/x/player/wbi/playurl?{q}")
        return _extract_stream_url(body)

    async def fetch_song_audio(self, query: str) -> tuple[bytes, str, str]:
        """Resolve a song keyword or BV id to (audio_bytes, clean_title, bvid)."""
        bvid, fallback_title = await self._resolve_song_bvid(query.strip())
        info = await self.video_info(bvid)
        title = HTML_EM_RE.sub("", str(info.get("title") or fallback_title)).strip()
        pages = info.get("pages")
        cid = int(pages[0].get("cid", 0)) if isinstance(pages, list) and pages else 0
        if not cid:
            raise RuntimeError(f"视频 {bvid} 缺少分P cid，无法提取音轨")
        stream_url = await self._fetch_audio_stream_url(bvid, cid)
        if not stream_url:
            raise RuntimeError(f"视频《{title}》({bvid}) 未返回可用音轨流地址")
        hdrs = {**(await self._headers()), "Referer": f"https://www.bilibili.com/video/{bvid}"}
        async with httpx.AsyncClient(timeout=45.0, trust_env=False, follow_redirects=True) as c:
            resp = await c.get(stream_url, headers=hdrs)
            resp.raise_for_status()
            raw = resp.content
        if len(raw) < 4096:
            raise RuntimeError(f"下载到的《{title}》音轨过小（{len(raw)} 字节）")
        return raw, title, bvid
