"""Feiyu GPU voice service client: POST /v1/speech -> poll -> download WAV."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx

VOICE_NAME = "feiyu"
SUBMIT_TIMEOUT_S = 20.0
POLL_TIMEOUT_S = 15.0
DOWNLOAD_TIMEOUT_S = 60.0
DEFAULT_MAX_WAIT_S = 120.0
DEFAULT_POLL_INTERVAL_S = 2.0
# 服务端 /v1/capabilities 声明 supports: cute / gentle；传中文或其它值会被 422 拒绝
ALLOWED_STYLES = ("cute", "gentle")
STYLE_ALIASES = {
    "可爱": "cute",
    "卖萌": "cute",
    "撒娇": "cute",
    "活泼": "cute",
    "元气": "cute",
    "开心": "cute",
    "温柔": "gentle",
    "平静": "gentle",
    "认真": "gentle",
    "稳重": "gentle",
    "冷淡": "gentle",
    "难过": "gentle",
}


def normalize_style(raw: str, default: str = "cute") -> str:
    """Map free-form mood words onto the styles the voice service actually provides."""
    text = (raw or "").strip()
    if text.lower() in ALLOWED_STYLES:
        return text.lower()
    mapped = STYLE_ALIASES.get(text)
    if mapped:
        return mapped
    fallback = (default or "cute").strip().lower()
    return fallback if fallback in ALLOWED_STYLES else "cute"


class FeiyuVoiceBackend:
    """Synthesize short TTS clips through the Feiyu voice GPU service."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        default_style: str = "cute",
        max_wait_s: float = DEFAULT_MAX_WAIT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._style = normalize_style(default_style)
        self._max_wait_s = max_wait_s
        self._poll = poll_interval_s

    def configure(
        self, *, base_url: str = "", api_key: str = "", default_style: str = ""
    ) -> None:
        """Hot-update Feiyu endpoint, API key, or default style from skill settings."""
        if base_url.strip():
            self._base = base_url.strip().rstrip("/")
        if api_key.strip():
            self._api_key = api_key.strip()
        if default_style.strip():
            self._style = normalize_style(default_style.strip(), self._style)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    async def _submit(self, client: httpx.AsyncClient, text: str, mood: str) -> str:
        payload = {
            "voice": VOICE_NAME,
            "text": text,
            "style": normalize_style(mood or self._style, self._style),
        }
        resp = await client.post(f"{self._base}/v1/speech", headers=self._headers(), json=payload)
        resp.raise_for_status()
        return str(resp.json().get("id") or "").strip()

    async def _wait(
        self, client: httpx.AsyncClient, job_id: str, wait_s: float | None = None
    ) -> None:
        deadline = time.monotonic() + (wait_s if wait_s is not None else self._max_wait_s)
        while True:
            row = await client.get(f"{self._base}/v1/jobs/{job_id}", headers=self._headers())
            row.raise_for_status()
            status = str(row.json().get("status") or "")
            if status == "success":
                return
            if status in ("failed", "interrupted"):
                err = str(row.json().get("error") or status)[:180]
                raise RuntimeError(f"语音/翻唱合成失败：{err}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"语音/翻唱合成超时（任务 {job_id}）")
            await asyncio.sleep(self._poll)

    async def capabilities(self) -> dict[str, Any]:
        """Return the service's advertised TTS voices and styles."""
        async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
            resp = await client.get(f"{self._base}/v1/capabilities", headers=self._headers())
            resp.raise_for_status()
            body = resp.json()
        return body if isinstance(body, dict) else {}

    async def health(self) -> dict[str, Any]:
        """Return the service health document (short timeout)."""
        async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
            resp = await client.get(f"{self._base}/health")
            resp.raise_for_status()
            body = resp.json()
        return body if isinstance(body, dict) else {}

    async def synthesize_tts(self, text: str, mood: str) -> str:
        """Return base64 WAV bytes for the given text."""
        async with httpx.AsyncClient(timeout=SUBMIT_TIMEOUT_S, trust_env=False) as client:
            job_id = await self._submit(client, text, mood)
            if not job_id:
                raise RuntimeError("声音服务没有返回任务编号")
            client.timeout = httpx.Timeout(POLL_TIMEOUT_S, connect=10.0)
            await self._wait(client, job_id)
            client.timeout = httpx.Timeout(DOWNLOAD_TIMEOUT_S, connect=10.0)
            audio = await client.get(
                f"{self._base}/v1/jobs/{job_id}/audio", headers=self._headers()
            )
            audio.raise_for_status()
        return base64.b64encode(audio.content).decode("ascii")

    async def _upload_asset(self, client: httpx.AsyncClient, audio_bytes: bytes) -> str:
        auth_hdr = {"Authorization": f"Bearer {self._api_key}"}
        files = {"file": ("song.m4a", audio_bytes, "audio/mp4")}
        resp = await client.post(f"{self._base}/v1/assets", headers=auth_hdr, files=files)
        resp.raise_for_status()
        asset_id = str(resp.json().get("id") or "").strip()
        if not asset_id:
            raise RuntimeError("上传原曲音轨失败：未返回素材 ID")
        return asset_id

    async def synthesize_cover(
        self,
        audio_bytes: bytes,
        *,
        pitch_shift: int | None = None,
        max_seconds: int = 240,
    ) -> str:
        """Upload source song audio and run HDemucs + RVC full-song AI cover on Feiyu GPU."""
        payload: dict[str, Any] = {
            "voice": VOICE_NAME,
            "max_seconds": max(20, min(max_seconds, 360)),
        }
        if pitch_shift is not None:
            payload["pitch_shift"] = max(-12, min(12, int(pitch_shift)))
        async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
            payload["audio_id"] = await self._upload_asset(client, audio_bytes)
            resp = await client.post(
                f"{self._base}/v1/cover", headers=self._headers(), json=payload
            )
            resp.raise_for_status()
            job_id = str(resp.json().get("id") or "").strip()
            if not job_id:
                raise RuntimeError("声音服务未返回翻唱任务编号")
            client.timeout = httpx.Timeout(POLL_TIMEOUT_S, connect=10.0)
            await self._wait(client, job_id, wait_s=max(self._max_wait_s, 360.0))
            client.timeout = httpx.Timeout(DOWNLOAD_TIMEOUT_S, connect=10.0)
            audio = await client.get(
                f"{self._base}/v1/jobs/{job_id}/audio", headers=self._headers()
            )
            audio.raise_for_status()
        return base64.b64encode(audio.content).decode("ascii")
