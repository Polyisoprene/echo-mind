"""OpenAI-compatible embeddings client (D15)."""

from __future__ import annotations

from typing import Any

import httpx

from echomind.core.config import EmbeddingConfig


class OpenAiEmbeddingGateway:
    """Minimal /embeddings client; inject a client for tests."""

    def __init__(
        self, config: EmbeddingConfig, client: httpx.AsyncClient | None = None
    ) -> None:
        if not config.enabled:
            raise ValueError("embedding endpoint is not configured")
        self._config = config
        self._client = client or httpx.AsyncClient(
            timeout=config.timeout_ms / 1000.0, trust_env=False
        )
        self._owns_client = client is None

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        payload: dict[str, Any] = {
            "model": self._config.model,
            "input": list(texts),
        }
        if self._config.dimensions > 0:
            payload["dimensions"] = self._config.dimensions
        response = await self._client.post(
            f"{self._config.base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {self._config.api_key}"},
            json=payload,
        )
        response.raise_for_status()
        rows = response.json().get("data", [])
        ordered = sorted(rows, key=lambda row: int(row.get("index", 0)))
        return tuple(tuple(float(x) for x in row["embedding"]) for row in ordered)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


__all__ = ["OpenAiEmbeddingGateway"]
