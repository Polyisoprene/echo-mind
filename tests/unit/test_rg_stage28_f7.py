"""Stage 28 RGR-F7: the OneBot HTTP caller must honour a dedicated HTTP token."""

from __future__ import annotations

from echomind.core.config import AppConfig, OneBotConnConfig
from echomind.main import build_http_caller

WS_TOKEN = "ws-token-value"  # noqa: S105
HTTP_TOKEN = "http-token-value"  # noqa: S105


def test_rg_f7_http_token_preferred() -> None:
    """A dedicated HTTP token must win over the WebSocket token."""
    cfg = AppConfig(
        onebot=OneBotConnConfig(
            http_url="http://127.0.0.1:3000",
            access_token=WS_TOKEN,
            http_token=HTTP_TOKEN,
        )
    )
    assert build_http_caller(cfg)._token == HTTP_TOKEN


def test_rg_f7_http_token_falls_back_to_ws() -> None:
    """With no dedicated HTTP token the WebSocket token remains the fallback."""
    cfg = AppConfig(onebot=OneBotConnConfig(access_token=WS_TOKEN))
    assert build_http_caller(cfg)._token == WS_TOKEN
