"""Multimodal vision describer backed by any OpenAI-compatible chat endpoint."""

from __future__ import annotations

import httpx

from echomind.core.config import GatewayEndpointConfig

VISION_TIMEOUT_S = 60.0


class OpenAiVisionDescriber:
    """Describe one or more images through the configured multimodal gateway."""

    def __init__(self, endpoint: GatewayEndpointConfig, model: str = "") -> None:
        self._endpoint = endpoint
        self._model = model or endpoint.model

    def reload_endpoint(self, endpoint: GatewayEndpointConfig) -> None:
        """Hot-swap the underlying multimodal gateway endpoint and model."""
        self._endpoint = endpoint
        self._model = endpoint.model

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._endpoint.api_key:
            headers["Authorization"] = f"Bearer {self._endpoint.api_key}"
        return headers

    def _payload(self, image_urls: tuple[str, ...], prompt: str) -> dict[str, object]:
        parts: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        parts.extend({"type": "image_url", "image_url": {"url": url}} for url in image_urls)
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": parts}],
            "temperature": 0.3,
            "max_tokens": 500,
        }

    async def describe(self, image_urls: tuple[str, ...], prompt: str) -> str:
        """Send the images to the vision model and return its description."""
        if not image_urls:
            return ""
        url = f"{self._endpoint.base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=VISION_TIMEOUT_S, trust_env=False) as client:
            resp = await client.post(
                url, headers=self._headers(), json=self._payload(image_urls, prompt)
            )
            resp.raise_for_status()
            body = resp.json()
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        return str(message.get("content") or "").strip()
