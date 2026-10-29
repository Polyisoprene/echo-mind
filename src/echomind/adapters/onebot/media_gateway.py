"""Pull QQ media (image / video / voice) out of chat history for the model."""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from echomind.adapters.onebot.media_codec import gif_to_storyboard_data_url
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import MediaAttachment
from echomind.domain.ports import IOneBotApiCaller

DOWNLOAD_TIMEOUT_S = 45.0
MAX_IMAGE_BYTES = 6 * 1024 * 1024
FFMPEG_TIMEOUT_S = 45
FRAME_MAX_WIDTH = 900


def _mime_of(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _find_media_item(items: object, kinds: tuple[str, ...]) -> dict[str, Any] | None:
    """Return the first attachment dict whose kind is wanted."""
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and str(item.get("kind", "")) in kinds:
            return item
    return None


def _frame_data_url(frame_path: str) -> str:
    path = Path(frame_path)
    if not path.exists():
        return ""
    return _to_data_url(path.read_bytes(), "image/jpeg")


def _cleanup_dir(path: Path | None) -> None:
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)


def _to_data_url(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


class OneBotMediaGateway:
    """Fetch the newest image / video / voice from a chat and normalize it."""

    def __init__(self, db: SqliteDatabase, caller: IOneBotApiCaller) -> None:
        self._db = db
        self._caller = caller

    async def _newest_media_json(
        self, chat_key: str, kinds: tuple[str, ...]
    ) -> dict[str, Any] | None:
        sql = (
            "SELECT media_json FROM chat_messages "
            "WHERE chat_key = ? AND is_self = 0 AND media_json != '' AND media_json != '[]' "
            "ORDER BY id DESC LIMIT 15"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key,))
            rows = await cursor.fetchall()
        for row in rows:
            found = _find_media_item(json.loads(str(row[0]) or "[]"), kinds)
            if found is not None:
                return found
        return None

    async def newest_media(self, chat_key: str, kind: str) -> MediaAttachment | None:
        """Return the newest attachment whose kind matches."""
        wanted = {"image": ("image",), "video": ("video_frames",), "voice": ("voice",)}
        item = await self._newest_media_json(chat_key, wanted.get(kind, (kind,)))
        if item is None:
            return None
        return MediaAttachment(
            kind=str(item.get("kind", "image")),  # type: ignore[arg-type]
            url=str(item.get("url", "")),
            local_path=str(item.get("local_path", "")),
            message_id=str(item.get("message_id", "")),
        )

    async def _download(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT_S, trust_env=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def load_data_url(self, item: MediaAttachment) -> str:
        """Download an image attachment and return it as a data URL (or 2x2 GIF storyboard)."""
        if item.data_url:
            return item.data_url
        if not item.url:
            return ""
        raw = await self._download(item.url)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            return ""
        mime = _mime_of(Path(item.url.split("?")[0]))
        if mime == "image/gif" or raw[:4] == b"GIF8":
            return gif_to_storyboard_data_url(raw) or _to_data_url(raw, "image/gif")
        return _to_data_url(raw, mime)

    def _extract_frames(self, video_path: str, count: int) -> list[str]:
        out_dir = Path(tempfile.mkdtemp(prefix="echo_frames_"))
        try:
            pattern = str(out_dir / "f_%02d.jpg")
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                video_path,
                "-vf",
                f"fps=1/3,scale={FRAME_MAX_WIDTH}:-2",
                "-frames:v",
                str(max(1, min(count, 8))),
                pattern,
            ]
            subprocess.run(  # noqa: S603 - 固定参数调用本机 ffmpeg
                cmd, check=True, timeout=FFMPEG_TIMEOUT_S, capture_output=True
            )
            return [_frame_data_url(str(p)) for p in sorted(out_dir.glob("f_*.jpg"))]
        finally:
            _cleanup_dir(out_dir)

    async def video_frame_urls(self, item: MediaAttachment, count: int) -> tuple[str, ...]:
        """Download a video, extract N evenly spaced JPEG frames, and clean up temp files."""
        source = item.url or item.local_path
        if not source:
            return ()
        tmp_dir: Path | None = None
        try:
            if source.startswith("http"):
                tmp_dir = Path(tempfile.mkdtemp(prefix="echo_video_"))
                video_file = tmp_dir / "clip.mp4"
                await asyncio.to_thread(video_file.write_bytes, await self._download(source))
            else:
                video_file = Path(source)
            raw_urls = await asyncio.to_thread(self._extract_frames, str(video_file), count)
            return tuple(u for u in raw_urls if u)
        finally:
            _cleanup_dir(tmp_dir)

    async def _try_fetch_ptt(self, mid: int | str) -> str:
        try:
            data = await self._caller.call_api("fetch_ptt_text", message_id=mid)
        except Exception:
            return ""
        if isinstance(data, dict):
            return str(data.get("text") or "").strip()
        return str(data or "").strip()

    async def _writeback_transcript(self, mid_str: str, text: str) -> None:
        sql = "UPDATE chat_messages SET text = ? WHERE mid = ? AND is_self = 0"
        async with self._db.connect() as conn:
            await conn.execute(sql, (f"[语音转文字] {text}", mid_str))
            await conn.commit()

    async def voice_to_text(
        self, item: MediaAttachment, *, retries: int = 4, delay_s: float = 1.2
    ) -> str:
        """Transcribe a QQ voice message, polling while NTQQ async Ptt2Text completes."""
        mid_str = item.message_id.strip()
        if not mid_str:
            return ""
        mid: int | str = int(mid_str) if mid_str.lstrip("-").isdigit() else mid_str
        for attempt in range(max(1, retries)):
            text = await self._try_fetch_ptt(mid)
            if text:
                await self._writeback_transcript(mid_str, text)
                return text
            if attempt + 1 < retries:
                await asyncio.sleep(delay_s)
        return ""

    async def cache_media_description(self, item: MediaAttachment, description: str) -> None:
        """Persist recognized image/video description into caption cache and chat_messages."""
        clean = description.strip()[:240]
        if not clean:
            return
        async with self._db.connect() as conn:
            if item.local_path and item.kind == "image":
                await conn.execute(
                    "INSERT OR REPLACE INTO image_caption_cache (md5, description, updated_at) "
                    "VALUES (?, ?, strftime('%s','now') * 1000)",
                    (item.local_path.upper(), clean),
                )
            if item.message_id:
                tag = "图片" if item.kind == "image" else "视频"
                await conn.execute(
                    "UPDATE chat_messages SET text = ? WHERE mid = ? AND is_self = 0",
                    (f"[{tag}:{clean[:110]}]", item.message_id),
                )
            await conn.commit()
