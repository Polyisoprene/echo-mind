"""Stage 29 A1: audit trail for console write operations."""

from __future__ import annotations

import time
from typing import Any

from starlette.requests import Request

_DDL = (
    "CREATE TABLE IF NOT EXISTS admin_audit ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, host TEXT NOT NULL, "
    "method TEXT NOT NULL, path TEXT NOT NULL, status INTEGER NOT NULL)"
)


async def write_audit(db: Any, request: Request, status: int) -> None:
    """Append one row describing who wrote what and how it ended."""
    host = str(request.client.host if request.client else "")
    async with db.connect() as conn:
        await conn.execute(_DDL)
        await conn.execute(
            "INSERT INTO admin_audit (ts, host, method, path, status) VALUES (?,?,?,?,?)",
            (int(time.time() * 1000), host, request.method, request.url.path, status),
        )
        await conn.commit()
