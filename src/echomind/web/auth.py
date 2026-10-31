"""Authorization for the console API: loopback stays open, remote needs the token."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
_HOST_NAMES = LOOPBACK_HOSTS | {"testserver"}
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _host_is_loopback(request: Request) -> bool:
    host = request.headers.get("host", "")
    name = host.split(":")[0].strip("[]").lower()
    return not name or name in _HOST_NAMES


def is_loopback_request(request: Request) -> bool:
    """True only when client, Host and (if present) Origin are all loopback."""
    client = request.client.host if request.client else ""
    if client not in LOOPBACK_HOSTS:
        return False
    if not _host_is_loopback(request):
        return False
    origin = request.headers.get("origin", "")
    if origin:
        name = (urlparse(origin).hostname or "").lower()
        if name not in LOOPBACK_HOSTS:
            return False
    return True


def _extract_request_token(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    header_tok = request.headers.get("x-echomind-token", "").strip()
    if header_tok:
        return header_tok
    return str(request.query_params.get("token", "")).strip()


def is_request_authorized(
    request: Request, auth_key: str, *, client_host: str | None = None
) -> bool:
    """Allow loopback/tunnel requests; require token for non-loopback /api/* calls.

    An unset token closes the API to non-loopback clients instead of opening it to
    everyone: a missing secret must not turn the console into a public API.
    """
    if not request.url.path.startswith("/api/"):
        return True
    host = client_host or (request.client.host if request.client else "127.0.0.1")
    loopback = host in LOOPBACK_HOSTS and _host_is_loopback(request)
    if not auth_key:
        return loopback
    token_ok = _extract_request_token(request) == auth_key
    if request.method.upper() in WRITE_METHODS:
        return token_ok
    if token_ok:
        return True
    return loopback
