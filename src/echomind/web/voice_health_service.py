"""Live probe of the Feiyu voice service so the console can show real capabilities."""

from __future__ import annotations

import time
from typing import Any

from echomind.core.bootstrap import EchoMindContainer

CACHE_TTL_MS = 20_000


class VoiceHealthService:
    """Expose the voice service's own capability document (cached briefly)."""

    def __init__(self, container: EchoMindContainer) -> None:
        self._c = container
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0

    def _offline(self, reason: str) -> dict[str, Any]:
        return {"ok": True, "online": False, "reason": reason[:160], "voices": []}

    def _summarize(self, caps: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
        tts = caps.get("tts")
        voices = [
            {
                "voice": str(v.get("voice", "")),
                "engine": str(v.get("engine", "")),
                "available": bool(v.get("available")),
                "styles": [str(s) for s in (v.get("styles") or [])],
                "package": str(v.get("package_id", "")),
            }
            for v in (tts if isinstance(tts, list) else [])
            if isinstance(v, dict)
        ]
        return {
            "ok": True,
            "online": True,
            "version": str(health.get("status", "")),
            "voices": voices,
        }

    async def probe(self) -> dict[str, Any]:
        """Return cached capabilities, refreshing at most every 20 seconds."""
        now_ms = int(time.time() * 1000)
        if self._cached is not None and now_ms - self._cached_at < CACHE_TTL_MS:
            return self._cached
        backend = self._c.voice_backend
        if backend is None:
            return self._offline("语音后端未装配")
        try:
            caps = await backend.capabilities()
            health = await backend.health()
        except Exception as exc:  # noqa: BLE001 - 探针失败不应影响控制台
            result = self._offline(f"{type(exc).__name__}: {exc}")
        else:
            result = self._summarize(caps, health)
        self._cached = result
        self._cached_at = now_ms
        return result
