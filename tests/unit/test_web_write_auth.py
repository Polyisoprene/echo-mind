"""Stage 29 A1: API writes always require the token; loopback keeps read access."""

from __future__ import annotations

from starlette.requests import Request

from echomind.web.app import is_request_authorized

TOKEN = "secret-token"  # noqa: S105 - test fixture, not a credential


def _request(method: str, path: str, token: str = "", host: str = "10.0.0.9") -> Request:
    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    scope = {
        "type": "http", "method": method, "path": path,
        "headers": headers, "query_string": b"",
        "client": (host, 12345), "server": ("testserver", 80),
        "scheme": "http", "root_path": "",
    }
    return Request(scope)


def test_loopback_reads_stay_open() -> None:
    assert is_request_authorized(_request("GET", "/api/mind/snapshot", host="127.0.0.1"), TOKEN)
    assert not is_request_authorized(_request("GET", "/api/mind/snapshot"), TOKEN)


def test_writes_require_the_token_even_on_loopback() -> None:
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert not is_request_authorized(_request(method, "/api/x", host="127.0.0.1"), TOKEN)
        assert is_request_authorized(_request(method, "/api/x", TOKEN, host="127.0.0.1"), TOKEN)


def test_remote_writes_need_the_token() -> None:
    assert not is_request_authorized(_request("POST", "/api/x"), TOKEN)
    assert is_request_authorized(_request("POST", "/api/x", TOKEN), TOKEN)


def test_non_api_paths_are_never_blocked() -> None:
    assert is_request_authorized(_request("POST", "/static/app.js", host="10.0.0.9"), TOKEN)
