"""OneBot v11 HTTP API caller (POST to the NapCat HTTP endpoint)."""

from __future__ import annotations

from typing import Any

import httpx


class OneBotHttpApiCaller:
    """Production IOneBotApiCaller sending POST requests to NapCat OneBot HTTP API."""

    def __init__(self, http_url: str, access_token: str = "") -> None:
        self._base = http_url.rstrip("/")
        self._token = access_token

    async def call_api(self, api: str, **data: Any) -> Any:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.post(f"{self._base}/{api}", headers=headers, json=data)
            resp.raise_for_status()
            body: dict[str, Any] = resp.json()
            return body.get("data", body)


__all__ = ["OneBotHttpApiCaller"]
