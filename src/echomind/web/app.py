"""FastAPI application factory: console pages, cognitive inspector API, static assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from echomind.core.bootstrap import EchoMindContainer
from echomind.web.audit import write_audit
from echomind.web.chat_service import ChatStreamService
from echomind.web.ext_routers import (
    build_llm_and_voice_router,
    build_persona_card_router,
    build_skill_config_router,
)
from echomind.web.identity_router import build_identity_router
from echomind.web.identity_service import IdentityConfigService
from echomind.web.llm_config_service import LlmConfigService
from echomind.web.mind_inspector_service import MindInspectorService
from echomind.web.probe_service import CognitiveProbeService
from echomind.web.skill_config_service import SkillConfigService
from echomind.web.social_router import build_social_router
from echomind.web.voice_health_service import VoiceHealthService

STATIC_DIR = Path(__file__).parent / "static"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


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
    """Allow loopback/tunnel requests; require token for non-loopback /api/* calls."""
    if not auth_key or not request.url.path.startswith("/api/"):
        return True
    token_ok = _extract_request_token(request) == auth_key
    if request.method.upper() in WRITE_METHODS:
        return token_ok
    if token_ok:
        return True
    host = client_host or (request.client.host if request.client else "127.0.0.1")
    return host in LOOPBACK_HOSTS


class FactUpsertPayload(BaseModel):
    """Request body for adding or locking an authoritative semantic fact."""

    chat_key: str = ""
    subject: str
    fact_text: str
    is_locked: bool = True


class PlasticTunePayload(BaseModel):
    """Request body for manually tuning a plastic or personality parameter."""

    key: str
    delta: float
    reason: str = "控制台手动调校"


class ProbePayload(BaseModel):
    """Request body for the cognitive probe playground."""

    chat_key: str = ""
    text: str
    sender_id: str = ""
    sender_name: str = ""


class BanPayload(BaseModel):
    """Request body for adding a forbidden phrase."""

    phrase: str
    reason: str = "控制台手动添加"


def _page_router() -> APIRouter:
    router = APIRouter()

    @router.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return router


def _mind_router(inspector: MindInspectorService, chat: ChatStreamService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/mind/snapshot")
    async def snapshot(chat_key: str = "") -> dict[str, Any]:
        return await inspector.build_snapshot(chat_key=chat_key)

    @router.get("/api/mind/sessions")
    async def sessions() -> dict[str, Any]:
        return {"ok": True, "sessions": await chat.list_sessions()}

    @router.get("/api/mind/turns")
    async def turns(chat_key: str = "", limit: int = 40) -> dict[str, Any]:
        return {"ok": True, "chat_key": chat_key, "turns": await chat.list_turns(chat_key, limit)}

    @router.get("/api/mind/messages")
    async def messages(chat_key: str = "", limit: int = 120) -> dict[str, Any]:
        target = chat_key or inspector.default_chat_key
        return {"ok": True, "chat_key": target, "messages": await chat.list_messages(target, limit)}

    return router


def _asset_router(chat: ChatStreamService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/mind/logs")
    async def logs(lines: int = 120) -> dict[str, Any]:
        return {"ok": True, "lines": await chat.tail_logs(lines)}

    @router.get("/api/mind/stickers")
    async def stickers() -> dict[str, Any]:
        return {"ok": True, "stickers": await chat.list_stickers()}

    @router.get("/api/mind/usage")
    async def usage() -> dict[str, Any]:
        return {"ok": True, "usage": await chat.usage_stats()}

    return router


def _persona_router(
    inspector: MindInspectorService, skill_cfg: SkillConfigService
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/mind/bans")
    async def bans() -> dict[str, Any]:
        return {"ok": True, "bans": await inspector.list_bans()}

    @router.get("/api/mind/traits")
    async def traits() -> dict[str, Any]:
        return {"ok": True, "traits": await inspector.list_traits()}

    @router.get("/api/mind/skills")
    async def skills() -> dict[str, Any]:
        await skill_cfg.sync_states()
        dc = len(inspector.deleted_skills())
        return {"ok": True, "groups": await inspector.list_skills(), "deleted_count": dc}

    @router.get("/api/mind/runtime")
    async def runtime() -> dict[str, Any]:
        return await inspector.runtime_info()

    return router


def _memory_action_router(inspector: MindInspectorService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/mind/facts")
    async def post_fact(payload: FactUpsertPayload) -> dict[str, Any]:
        return await inspector.upsert_authoritative_fact(
            chat_key=payload.chat_key,
            subject=payload.subject,
            fact_text=payload.fact_text,
            is_locked=payload.is_locked,
        )

    @router.delete("/api/mind/episodic/{card_id}")
    async def delete_episodic(card_id: int) -> dict[str, Any]:
        return await inspector.delete_episodic_card(card_id)

    @router.delete("/api/mind/facts/{fact_id}")
    async def delete_fact(fact_id: int) -> dict[str, Any]:
        return await inspector.delete_semantic_fact(fact_id)

    @router.delete("/api/mind/rules/{rule_id}")
    async def delete_rule(rule_id: int) -> dict[str, Any]:
        return await inspector.delete_procedural_rule(rule_id)

    @router.post("/api/mind/plastic/tune")
    async def tune(payload: PlasticTunePayload) -> dict[str, Any]:
        return await inspector.manual_tune_plastic_param(
            key=payload.key, delta=payload.delta, reason=payload.reason
        )

    return router


def _governance_router(inspector: MindInspectorService, probe: CognitiveProbeService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/mind/tick")
    async def tick() -> dict[str, Any]:
        return await inspector.trigger_autonomous_tick()

    @router.post("/api/mind/bans")
    async def add_ban(payload: BanPayload) -> dict[str, Any]:
        return await inspector.add_ban(payload.phrase, payload.reason)

    @router.delete("/api/mind/bans/{phrase}")
    async def remove_ban(phrase: str) -> dict[str, Any]:
        return await inspector.remove_ban(phrase)

    @router.delete("/api/mind/traits/{trait_id}")
    async def delete_trait(trait_id: int) -> dict[str, Any]:
        return await inspector.delete_trait(trait_id)

    @router.post("/api/mind/probe")
    async def run_probe(payload: ProbePayload) -> dict[str, Any]:
        return await probe.probe(
            payload.chat_key, payload.text, payload.sender_id, payload.sender_name
        )

    return router


async def no_cache_static(request: Request, call_next: Any) -> Response:
    """Keep the console's JS/CSS fresh so UI fixes show up without a hard refresh."""
    response: Response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


def build_guard_and_cache_middleware(auth_key: str, db: Any = None) -> Any:
    """Create an HTTP middleware enforcing token auth on writes, plus static no-cache."""

    async def _guard_and_cache(request: Request, call_next: Any) -> Response:
        is_write = request.method.upper() in WRITE_METHODS and request.url.path.startswith("/api/")
        sink = db() if callable(db) else db
        if not is_request_authorized(request, auth_key):
            if is_write and sink is not None:
                await write_audit(sink, request, 401)
            return Response(
                content='{"ok":false,"error":"unauthorized"}',
                status_code=401,
                media_type="application/json",
            )
        response = await no_cache_static(request, call_next)
        if is_write and sink is not None:
            await write_audit(sink, request, response.status_code)
        return response

    return _guard_and_cache


def create_web_app(
    container: EchoMindContainer,
    log_path: Path | None = None,
    config_path: Path | None = None,
    *,
    auth_key: str = "",
) -> FastAPI:
    """Create and wire the FastAPI application around EchoMindContainer."""
    app = FastAPI(title="EchoMind Console", version="2.0.0")
    inspector = MindInspectorService(container)
    chat = ChatStreamService(container, log_path or Path("data/console.log"))
    probe = CognitiveProbeService(container)
    llm = LlmConfigService(container, config_path or Path("data/config.json"))
    voice = VoiceHealthService(container)
    skill_cfg = SkillConfigService(container)

    @app.get("/api/session/token")
    async def _session_token(request: Request) -> dict[str, str]:
        """Hand the console its token, but only to loopback clients."""
        host = request.client.host if request.client else "127.0.0.1"
        return {"token": auth_key if auth_key and host in LOOPBACK_HOSTS else ""}

    app.include_router(_page_router())
    app.include_router(_mind_router(inspector, chat))
    app.include_router(_asset_router(chat))
    app.include_router(_persona_router(inspector, skill_cfg))
    app.include_router(build_persona_card_router(llm, inspector))
    app.include_router(build_social_router(container))
    identity = IdentityConfigService(config_path or Path("data/config.json"), container)
    app.include_router(build_identity_router(identity))
    app.include_router(_memory_action_router(inspector))
    app.include_router(build_llm_and_voice_router(llm, chat, voice))
    app.include_router(build_skill_config_router(skill_cfg))
    app.include_router(_governance_router(inspector, probe))
    app.middleware("http")(build_guard_and_cache_middleware(auth_key, container.db))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app
