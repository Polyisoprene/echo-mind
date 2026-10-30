"""High-availability Failover LLM Gateway Client implementing ILlmGateway with SQLite tracing."""

from __future__ import annotations

import os
import time
from typing import Any, Protocol

import httpx

from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import GatewayEndpointConfig


class IHttpPostTransport(Protocol):
    """Minimal async HTTP transport protocol for zero-network unit testing (DIP & LSP)."""

    async def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_s: float
    ) -> dict[str, Any]: ...


class HttpxPostTransport:
    """Production httpx implementation of IHttpPostTransport."""

    async def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_s: float
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout_s, trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data


def _extract_token_counts(raw_resp: dict[str, Any]) -> tuple[int, int, int]:
    usage = raw_resp.get("usage", {})
    if not isinstance(usage, dict):
        return 0, 0, 0
    prompt_tok = int(usage.get("prompt_tokens", 0))
    comp_tok = int(usage.get("completion_tokens", 0))
    details = usage.get("prompt_tokens_details", {})
    cached = int(details.get("cached_tokens", 0)) if isinstance(details, dict) else 0
    return prompt_tok, cached, comp_tok


def _build_chain(
    primary: GatewayEndpointConfig,
    fallback: GatewayEndpointConfig,
    extra: tuple[GatewayEndpointConfig, ...] = (),
) -> tuple[GatewayEndpointConfig, ...]:
    candidates = [primary, *extra, fallback]
    seen: set[tuple[str, str]] = set()
    chain: list[GatewayEndpointConfig] = []
    for ep in candidates:
        key = (ep.base_url.rstrip("/"), ep.model)
        if key not in seen:
            seen.add(key)
            chain.append(ep)
    return tuple(chain)


class FailoverLlmGateway:
    """Adapter satisfying ILlmGateway with N-way automatic failover and trace logging."""

    def __init__(
        self,
        primary: GatewayEndpointConfig,
        fallback: GatewayEndpointConfig,
        db: SqliteDatabase,
        transport: IHttpPostTransport | None = None,
        *,
        extra_fallbacks: tuple[GatewayEndpointConfig, ...] = (),
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._chain = _build_chain(primary, fallback, extra_fallbacks)
        self._db = db
        self._transport: IHttpPostTransport = transport if transport else HttpxPostTransport()

    def endpoints(self) -> tuple[GatewayEndpointConfig, GatewayEndpointConfig]:
        """Return the currently active primary and first fallback endpoints."""
        return self._primary, self._fallback

    def endpoint_chain(self) -> tuple[GatewayEndpointConfig, ...]:
        """Return the full ordered failover endpoint chain."""
        return self._chain

    async def reload_endpoints(
        self,
        primary: GatewayEndpointConfig,
        fallback: GatewayEndpointConfig,
        *,
        extra_fallbacks: tuple[GatewayEndpointConfig, ...] = (),
    ) -> None:
        """Hot-swap gateway endpoints and full fallback chain without restarting."""
        self._primary = primary
        self._fallback = fallback
        self._chain = _build_chain(primary, fallback, extra_fallbacks)

    async def _record_trace(
        self,
        gw: GatewayEndpointConfig,
        elapsed_ms: int,
        raw_resp: dict[str, Any],
        is_failover: bool,
        chat_key: str,
    ) -> None:
        p_tok, c_tok, o_tok = _extract_token_counts(raw_resp)
        now_ms = int(time.time() * 1000)
        sql = (
            "INSERT INTO llm_traces "
            "(ts, session_id, gateway_name, model_name, elapsed_ms, prompt_tokens, "
            "cached_tokens, completion_tokens, is_failover, chat_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        async with self._db.connect() as conn:
            await conn.execute(
                sql,
                (
                    now_ms,
                    "",
                    gw.name,
                    gw.model,
                    elapsed_ms,
                    p_tok,
                    c_tok,
                    o_tok,
                    int(is_failover),
                    chat_key,
                ),
            )
            await conn.commit()

    async def _call_endpoint(
        self,
        gw: GatewayEndpointConfig,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
        *,
        thinking_off: bool = False,
        json_mode: bool = False,
        model_override: str = "",
    ) -> dict[str, Any]:
        url = f"{gw.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {gw.api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": gw.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if model_override:
            payload["model"] = model_override
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if not thinking_off and os.getenv("ECHOMIND_THINKING", "on") != "off":
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = os.getenv("ECHOMIND_REASONING_EFFORT", "low")
        return await self._transport.post_json(url, headers, payload, gw.timeout_ms / 1000.0)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.6,
        max_tokens: int = 800,
        thinking_off: bool = False,
        *,
        chat_key: str = "",
        json_mode: bool = False,
        model_override: str = "",
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        for idx, gw in enumerate(self._chain):
            t0 = time.monotonic()
            try:
                resp = await self._call_endpoint(
                    gw, messages, tools, temperature, max_tokens, thinking_off=thinking_off,
                    json_mode=json_mode, model_override=model_override
                )
                elapsed = int((time.monotonic() - t0) * 1000)
                await self._record_trace(
                    gw, elapsed, resp, is_failover=(idx > 0), chat_key=chat_key
                )
                return resp
            except Exception as exc:
                last_exc = exc
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No LLM gateway endpoints configured")
