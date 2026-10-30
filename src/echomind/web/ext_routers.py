"""Modular FastAPI routers for LLM config, Voice health, Base Persona Card, and Skill management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from echomind.web.chat_service import ChatStreamService
from echomind.web.llm_config_service import LlmConfigService
from echomind.web.mind_inspector_service import MindInspectorService
from echomind.web.skill_config_service import SkillConfigService
from echomind.web.voice_health_service import VoiceHealthService


class SkillConfigPayload(BaseModel):
    """Request body for saving one skill's configuration."""

    values: dict[str, str] = {}


class LlmConfigPayload(BaseModel):
    """Request body for hot-applying LLM gateway, providers & fallback chain configuration."""

    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout_ms: int | None = None
    fallback_model: str | None = None
    fallback_base_url: str | None = None
    fallback_api_key: str | None = None
    temperature: float | None = None
    providers: list[dict[str, Any]] | None = None
    fallback_models: list[dict[str, Any]] | None = None


class BondTunePayload(BaseModel):
    """Request body for manually adjusting a member's affinity or trust score."""

    affinity_score: float
    chat_key: str = ""
    user_name: str = ""
    is_rival: bool | None = None
    trust_score: float | None = None


class PersonaCardPayload(BaseModel):
    """Request body for updating the initial base persona card."""

    bot_name: str = ""
    role_text: str = ""


def build_skill_config_router(cfg_service: SkillConfigService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/mind/skills/configs")
    async def list_skill_configs() -> dict[str, Any]:
        return {"ok": True, "configs": await cfg_service.list_configs()}

    @router.put("/api/mind/skills/configs/{skill}")
    async def save_skill_config(skill: str, payload: SkillConfigPayload) -> dict[str, Any]:
        return await cfg_service.save(skill, payload.values)

    @router.post("/api/mind/skills/{name}/toggle")
    async def toggle_skill(name: str) -> dict[str, Any]:
        return await cfg_service.toggle_tool(name)

    @router.delete("/api/mind/skills/{name}")
    async def delete_skill(name: str) -> dict[str, Any]:
        return await cfg_service.delete_tool(name)

    @router.post("/api/mind/skills/restore")
    async def restore_skills() -> dict[str, Any]:
        return await cfg_service.restore_deleted()

    return router


def build_llm_and_voice_router(
    llm: LlmConfigService, chat: ChatStreamService, voice: VoiceHealthService
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/mind/llm")
    async def get_llm_config() -> dict[str, Any]:
        return llm.read()

    @router.put("/api/mind/llm")
    async def put_llm_config(payload: LlmConfigPayload) -> dict[str, Any]:
        patch = {
            "provider": payload.provider,
            "model": payload.model,
            "baseUrl": payload.base_url,
            "apiKey": payload.api_key,
            "timeoutMs": payload.timeout_ms,
            "fallbackModel": payload.fallback_model,
            "fallbackBaseUrl": payload.fallback_base_url,
            "fallbackApiKey": payload.fallback_api_key,
            "temperature": payload.temperature,
            "providers": payload.providers,
            "fallbackModels": payload.fallback_models,
        }
        return await llm.apply(patch)

    @router.get("/api/mind/voice")
    async def voice_health() -> dict[str, Any]:
        return await voice.probe()

    @router.get("/api/mind/llm/traces")
    async def get_llm_traces(limit: int = 60) -> dict[str, Any]:
        return {"ok": True, "traces": await chat.list_llm_traces(limit)}

    return router


def build_persona_card_router(llm: LlmConfigService, inspector: MindInspectorService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/mind/persona-card")
    async def get_persona_card() -> dict[str, Any]:
        return llm.read_persona()

    @router.put("/api/mind/persona-card")
    async def put_persona_card(payload: PersonaCardPayload) -> dict[str, Any]:
        return llm.apply_persona(payload.bot_name, payload.role_text)

    @router.post("/api/mind/persona-card/reconcile")
    async def reconcile_persona() -> dict[str, Any]:
        return await llm.reconcile_persona_memory()

    @router.put("/api/mind/bonds/{user_id}")
    async def put_social_bond(user_id: str, payload: BondTunePayload) -> dict[str, Any]:
        return await inspector.update_social_bond(
            user_id,
            payload.affinity_score,
            chat_key=payload.chat_key,
            user_name=payload.user_name,
            is_rival=payload.is_rival,
            trust_score=payload.trust_score,
        )

    return router
