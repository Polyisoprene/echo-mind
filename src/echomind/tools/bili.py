"""Bilibili skills: search videos, read a video, browse popular (cookie configurable)."""

from __future__ import annotations

from typing import Any

from echomind.domain.models import SkillConfigField
from echomind.domain.ports import IBiliClient

BILI_FIELDS = (
    SkillConfigField(
        key="sessdata",
        label="SESSDATA",
        kind="password",
        secret=True,
        placeholder="浏览器登录B站 → F12 → Cookie → 复制 SESSDATA 的值",
        help="不填也能搜视频看热门，但动态/个人相关接口会要求登录态。",
    ),
    SkillConfigField(key="bili_jct", label="bili_jct", kind="password", secret=True),
    SkillConfigField(key="dedeuserid", label="DedeUserID", kind="password", secret=True),
)


def _fmt_duration(raw: Any) -> str:
    """搜索接口给的是 "3:05"，详情接口给的是秒数，两种都要能吃。"""
    if isinstance(raw, str):
        text = raw.strip()
        if ":" in text:
            return text
        try:
            raw = int(text)
        except ValueError:
            return ""
    try:
        total = int(raw)
    except (TypeError, ValueError):
        return ""
    return f"{total // 60}:{total % 60:02d}"


class BiliSearchTool:
    """Search B站 videos by keyword."""

    category = "信息探索"
    config_key = "bili"

    def __init__(self, client: IBiliClient) -> None:
        self._client = client

    def config_fields(self) -> tuple[SkillConfigField, ...]:
        return BILI_FIELDS

    @property
    def name(self) -> str:
        return "bili_search"

    @property
    def description(self) -> str:
        return "在 B站搜索视频，返回标题、UP主、播放量、时长和 BV 号（想了解某个梗/番的原片时用）。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "description": "返回几条，默认 5"},
            },
            "required": ["keyword"],
        }

    async def execute(self, _chat_key: str, args: dict[str, Any]) -> str:
        keyword = str(args.get("keyword", "")).strip()
        if not keyword:
            return "搜索词为空"
        try:
            limit = max(1, min(int(args.get("limit", 5)), 10))
        except (TypeError, ValueError):
            limit = 5
        items = await self._client.search_videos(keyword, limit)
        if not items:
            return f"B站没搜到『{keyword}』的结果。"
        lines = []
        for item in items:
            title = (
                str(item.get("title", "")).replace('<em class="keyword">', "").replace("</em>", "")
            )
            bvid = str(item.get("bvid", "")).strip()
            url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""
            lines.append(
                f"- 《{title}》 ｜ UP主:{item.get('author', '')} ｜ 播放:{item.get('play', 0)} "
                f"｜ 时长:{_fmt_duration(item.get('duration'))} ｜ {url}"
            )
        return f"🎬 B站搜索『{keyword}』：\n" + "\n".join(lines)


class BiliVideoTool:
    """Read one video's metadata by BV id."""

    category = "信息探索"
    config_key = "bili"

    def __init__(self, client: IBiliClient) -> None:
        self._client = client

    def config_fields(self) -> tuple[SkillConfigField, ...]:
        return BILI_FIELDS

    @property
    def name(self) -> str:
        return "bili_video"

    @property
    def description(self) -> str:
        return "查看某个 BV 号视频的详细信息（标题、UP主、简介、播放、点赞、分P）。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"bvid": {"type": "string", "description": "形如 BV1xx411c7mD"}},
            "required": ["bvid"],
        }

    async def execute(self, _chat_key: str, args: dict[str, Any]) -> str:
        bvid = str(args.get("bvid", "")).strip()
        if not bvid:
            return "缺少 bvid"
        data = await self._client.video_info(bvid)
        if not data:
            return f"没查到 {bvid} 的视频信息（可能已失效或需要登录 Cookie）。"
        raw_owner = data.get("owner")
        owner_name = str(raw_owner.get("name", "")) if isinstance(raw_owner, dict) else ""
        raw_stat = data.get("stat")
        stat = raw_stat if isinstance(raw_stat, dict) else {}
        return (
            f"🎬 {data.get('title', '')}\n"
            f"UP主：{owner_name} ｜ 时长：{_fmt_duration(data.get('duration'))}\n"
            f"播放：{stat.get('view', 0)} ｜ 点赞：{stat.get('like', 0)} "
            f"｜ 弹幕：{stat.get('danmaku', 0)}\n"
            f"简介：{str(data.get('desc', ''))[:160]}"
        )


def _popular_line(item: dict[str, Any]) -> str:
    owner = item.get("owner")
    stat = item.get("stat")
    name = str(owner.get("name", "")) if isinstance(owner, dict) else ""
    views = stat.get("view", 0) if isinstance(stat, dict) else 0
    bvid = str(item.get("bvid", "")).strip()
    url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""
    return f"- 《{item.get('title', '')}》 ｜ UP主:{name} ｜ 播放:{views} ｜ {url}"


class BiliPopularTool:
    """Browse the B站 popular list."""

    category = "信息探索"
    config_key = "bili"

    def __init__(self, client: IBiliClient) -> None:
        self._client = client

    def config_fields(self) -> tuple[SkillConfigField, ...]:
        return BILI_FIELDS

    @property
    def name(self) -> str:
        return "bili_popular"

    @property
    def description(self) -> str:
        return "看看 B站当前热门视频榜（想主动找话题时用）。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "返回几条，默认 5"}},
            "required": [],
        }

    async def execute(self, _chat_key: str, args: dict[str, Any]) -> str:
        try:
            limit = max(1, min(int(args.get("limit", 5)), 10))
        except (TypeError, ValueError):
            limit = 5
        items = await self._client.popular(limit)
        if not items:
            return "暂时拿不到 B站热门榜。"
        lines = [_popular_line(i) for i in items]
        return "🔥 B站热门：\n" + "\n".join(lines)
