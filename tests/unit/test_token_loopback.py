"""D13: the token endpoint only trusts requests whose Host/Origin are loopback."""

from __future__ import annotations

from starlette.requests import Request

from echomind.web.auth import is_loopback_request


def _request(
    client: str = "127.0.0.1", host: str = "127.0.0.1:3310", origin: str = ""
) -> Request:
    headers = [(b"host", host.encode())]
    if origin:
        headers.append((b"origin", origin.encode()))
    scope = {
        "type": "http", "method": "GET", "path": "/api/session/token",
        "headers": headers, "query_string": b"",
        "client": (client, 12345), "server": ("testserver", 80),
        "scheme": "http", "root_path": "",
    }
    return Request(scope)


def test_loopback_host_passes() -> None:
    assert is_loopback_request(_request())


def test_public_host_is_rejected_even_from_loopback_client() -> None:
    assert not is_loopback_request(_request(host="evil.example:443"))


def test_public_origin_is_rejected() -> None:
    assert not is_loopback_request(
        _request(host="127.0.0.1:3310", origin="https://evil.example")
    )


def test_remote_client_is_rejected() -> None:
    assert not is_loopback_request(_request(client="10.0.0.9"))
