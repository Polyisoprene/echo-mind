"""Media perception tools: look at images and watch short videos."""

from __future__ import annotations

from typing import Any

from echomind.domain.ports import IQQMediaGateway, IVisionDescriber

# 感知层只负责"看清"，不负责"怎么说话"：
# 语气、人称、亲昵程度全部由 CognitiveFrame 的 7 维性格与当前情绪在主模型侧决定。
IMAGE_PROMPT = (
    "客观描述这张图片：主体是谁/什么、表情与动作、画面中的文字，"
    "以及它是否属于表情包梗图。只陈述事实，不评价、不寒暄，150 字以内。"
)
VIDEO_PROMPT = (
    "下面是同一个视频按时间顺序抽取的若干帧画面。客观概括视频内容：主体、"
    "关键动作与画面变化。只陈述事实，不评价、不寒暄，150 字以内。"
)


class LookAtImageTool:
    """Let the agent actually see the newest image posted in the chat."""

    def __init__(self, media: IQQMediaGateway, vision: IVisionDescriber) -> None:
        self._media = media
        self._vision = vision

    @property
    def category(self) -> str:
        return "媒体感知"

    @property
    def name(self) -> str:
        return "look_at_image"

    @property
    def description(self) -> str:
        return "查看群里最新发来的图片内容（识别主体、画面文字与表情包含义）。"

    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        item = await self._media.newest_media(chat_key, "image")
        if item is None:
            return "最近没有找到可以看的图片。"
        data_url = await self._media.load_data_url(item)
        if not data_url:
            return "图片下载失败，可能链接已过期。"
        text = await self._vision.describe((data_url,), IMAGE_PROMPT)
        if text:
            await self._media.cache_media_description(item, text)
        return text or "图片看得不太清楚。"


class WatchVideoTool:
    """Sample frames from the newest video and describe them."""

    def __init__(self, media: IQQMediaGateway, vision: IVisionDescriber) -> None:
        self._media = media
        self._vision = vision

    @property
    def category(self) -> str:
        return "媒体感知"

    @property
    def name(self) -> str:
        return "watch_video"

    @property
    def description(self) -> str:
        return "观看群里最新发来的视频，自动抽取若干帧并概括视频内容。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "frames": {"type": "integer", "description": "抽取几帧，默认 4，最多 8"}
            },
            "required": [],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        item = await self._media.newest_media(chat_key, "video")
        if item is None:
            return "最近没有找到可以看的视频。"
        try:
            count = int(args.get("frames", 4))
        except (TypeError, ValueError):
            count = 4
        frames = await self._media.video_frame_urls(item, max(1, min(count, 8)))
        if not frames:
            return "视频抽帧失败，可能文件已过期或格式不支持。"
        text = await self._vision.describe(frames, VIDEO_PROMPT)
        if text:
            await self._media.cache_media_description(item, text)
        return text or "视频画面没看清。"
