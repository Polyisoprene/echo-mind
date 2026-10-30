"""Stage 29 A5: identity configuration endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from echomind.web.identity_service import IdentityConfigService


class IdentityPayload(BaseModel):
    """Console-submitted identity settings."""

    bot_name: str = ""
    keywords: list[str] = []
    self_qq: str = ""
    groups: list[str] = []
    private: list[str] = []
    default_group: str = ""


def build_identity_router(service: IdentityConfigService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/config/identity")
    async def read_identity() -> dict[str, Any]:
        return service.read()

    @router.post("/api/config/identity")
    async def save_identity(payload: IdentityPayload) -> dict[str, Any]:
        return service.save(payload.model_dump())

    return router
