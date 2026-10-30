"""Stage 29 A5: identity configuration endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
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
    operators: list[str] = []
    probe_model: str = ""


def build_identity_router(service: IdentityConfigService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/config/identity")
    async def read_identity() -> dict[str, Any]:
        return service.read()

    @router.post("/api/config/identity")
    async def save_identity(payload: IdentityPayload) -> dict[str, Any]:
        try:
            return service.save(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
