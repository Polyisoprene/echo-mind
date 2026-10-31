"""M6.1 Production Application Entrypoint assembling Container, Live WS Runtime & FastAPI."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.media.bili import BiliClient
from echomind.adapters.media.feiyu import FeiyuVoiceBackend
from echomind.adapters.media.vision import OpenAiVisionDescriber
from echomind.adapters.onebot.bot_bridge import OneBotV11Bridge
from echomind.adapters.onebot.enrichers import PerceptEnrichmentPipeline
from echomind.adapters.onebot.forward_expander import ReadForwardTool
from echomind.adapters.onebot.live_client import OneBotHttpApiCaller, OneBotLiveRuntime
from echomind.adapters.onebot.media_gateway import OneBotMediaGateway
from echomind.core.bootstrap import EchoMindContainer
from echomind.core.config import AppConfig, load_config_from_json
from echomind.mind.memory_budget import set_consolidation_budget, set_consolidation_thinking
from echomind.mind.naming import BotNaming, set_bot_naming
from echomind.mind.probe_runtime import set_probe_model
from echomind.mind.subconscious_probe import SubconsciousChordProbe
from echomind.runtime.agent_runner import AgentSessionRunner
from echomind.runtime.prompt_composer import PromptComposer
from echomind.runtime.qzone_scheduler import QzoneMoodShowcaseScheduler
from echomind.runtime.scheduler import CognitiveHeartbeatScheduler
from echomind.tools.bili import BiliPopularTool, BiliSearchTool, BiliVideoTool
from echomind.tools.cnmeme_wiki import CnMemeWikiClient
from echomind.tools.explore_and_voice import (
    BiliSearchBackend,
    CompositeSearchBackend,
    HolyWebSearchTool,
)
from echomind.tools.media_vision import LookAtImageTool, WatchVideoTool
from echomind.tools.member_memory import RecallMemoryTool, RememberMemberTool
from echomind.tools.messaging_and_group import (
    GetGroupMembersTool,
    SendMessageTool,
    SendPokeTool,
    SendStickerTool,
)
from echomind.tools.qzone_and_profile import QzoneAndProfileTool
from echomind.tools.voice_tools import FeiyuCoverTool, FeiyuSayTool, ReadVoiceTool
from echomind.web.app import build_guard_and_cache_middleware, create_web_app
from echomind.web.skill_config_service import SkillConfigService


async def create_production_app(
    db_path: Path | None = None,
    config_path: Path | None = None,
) -> tuple[FastAPI, EchoMindContainer]:
    """Bootstrap the full production EchoMind container and FastAPI ASGI application."""
    cfg = load_config_from_json(config_path) if config_path else AppConfig()
    set_bot_naming(BotNaming(name=cfg.bot_name, aliases=tuple(cfg.keywords)))
    set_probe_model(cfg.probe_model)
    set_consolidation_budget(cfg.memory_budget)
    set_consolidation_thinking(cfg.memory_thinking)
    resolved_db = db_path if db_path is not None else Path("data/echomind.db")
    first_group = cfg.allowed_groups[0] if cfg.allowed_groups else "10002002"
    container = await EchoMindContainer.create(
        db_path=resolved_db,
        default_chat_key=f"group:{first_group}",
        operator_ids=cfg.operator_ids,
    )
    app = create_web_app(container, config_path=config_path, auth_key=cfg.auth_key)
    return app, container


def _register_skill_tools(
    cfg: AppConfig, container: EchoMindContainer,
    caller: OneBotHttpApiCaller, bridge: OneBotV11Bridge,
) -> None:
    """Register every runtime skill, grouped by category (社交 / 媒体 / 语音 / 探索)."""
    reg, m, s = container.registry, container.memory_repo, container.skill_config_store
    media = OneBotMediaGateway(container.db, caller)
    vision = OpenAiVisionDescriber(cfg.primary_llm)
    voice = FeiyuVoiceBackend(cfg.feiyu_base_url, cfg.feiyu_api_key, default_style=cfg.feiyu_style)
    container.vision_describer, container.voice_backend = vision, voice

    async def _bili_values() -> dict[str, str]:
        return await s.get_skill_config("bili") if s else {}

    bili = BiliClient(cookie_provider=_bili_values)
    search_be = CompositeSearchBackend((CnMemeWikiClient(), BiliSearchBackend(bili)))
    for tool in (
        SendMessageTool(bridge), SendStickerTool(bridge), SendPokeTool(bridge),
        GetGroupMembersTool(bridge), RememberMemberTool(m, m), RecallMemoryTool(m),
        QzoneAndProfileTool(caller),
        LookAtImageTool(media, vision), WatchVideoTool(media, vision),
        ReadVoiceTool(media), ReadForwardTool(caller, container.db),
        BiliSearchTool(bili), BiliVideoTool(bili), BiliPopularTool(bili),
        HolyWebSearchTool(search_be), FeiyuSayTool(voice, bridge),
        FeiyuCoverTool(voice, bili, bridge),
    ):
        reg.register_tool(tool)


def _build_scheduler(
    container: EchoMindContainer,
    caller: OneBotHttpApiCaller,
    llm: FailoverLlmGateway,
    bridge: OneBotV11Bridge,
) -> CognitiveHeartbeatScheduler:
    qzone_sched = (
        QzoneMoodShowcaseScheduler(
            caller=caller,
            llm=llm,
            working_store=container.working_store,
            memory_reader=container.memory_repo,
            config_store=container.skill_config_store,
            default_chat_key=container.default_chat_key,
            sender=bridge,
        )
        if container.skill_config_store is not None
        else None
    )
    return CognitiveHeartbeatScheduler(
        db=container.db,
        mem_reader=container.memory_repo,
        cognitive=container.cognitive_facade,
        sender=bridge,
        qzone_scheduler=qzone_sched,
        registry=container.registry,
        mem_writer=container.memory_repo,
        working_store=container.working_store,
        trace_store=container.trace_store,
        llm=llm,
        persona_layers=container.persona_layers,
    )


def build_http_caller(cfg: AppConfig) -> OneBotHttpApiCaller:
    """Build the OneBot HTTP caller, preferring the dedicated HTTP token when set."""
    token = cfg.onebot.http_token_value or cfg.onebot.access_token_value
    return OneBotHttpApiCaller(cfg.onebot.http_url, token)


def _build_live_runtime(cfg: AppConfig, container: EchoMindContainer) -> OneBotLiveRuntime:
    caller = build_http_caller(cfg)
    container.onebot_caller = caller
    bridge = OneBotV11Bridge(caller, container.db)
    _register_skill_tools(cfg, container, caller, bridge)
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, container.db, extra_fallbacks=cfg.fallback_chain
    )
    container.llm_gateway = llm
    container.cognitive_facade.set_subconscious_probe(
        SubconsciousChordProbe(llm)
    )
    composer = PromptComposer(role_text=cfg.role_text, bot_name=cfg.bot_name)
    container.prompt_composer = composer
    for sensor in container.registry.sensors:
        set_fn = getattr(sensor, "set_bot_names", None)
        if callable(set_fn):
            set_fn((cfg.bot_name, *cfg.keywords))
    runner = AgentSessionRunner(
        cognitive=container.cognitive_facade, llm=llm, registry=container.registry,
        sender=bridge, composer=composer, temperature=cfg.temperature,
        trace_store=container.trace_store, event_bus=container.event_bus,
    )
    scheduler = _build_scheduler(container, caller, llm, bridge)
    container.scheduler = scheduler
    runtime = OneBotLiveRuntime(
        ws_url=cfg.onebot.ws_url, http_url=cfg.onebot.http_url,
        access_token=cfg.onebot.access_token_value, self_id=cfg.self_qq or "10003003",
        allowed_groups=cfg.allowed_groups or ("10002002",),
        allowed_private=cfg.allowed_private, operator_ids=cfg.operator_ids,
        db=container.db, pipeline=PerceptEnrichmentPipeline(container.registry.sensors),
        cognitive=container.cognitive_facade, runner=runner, scheduler=scheduler, debounce_s=2.0,
        bond_store=container.bond_depth_store, bot_names=tuple(cfg.keywords),
    )
    container.onebot_runtime = runtime
    return runtime


def _instance_config_path() -> Path:
    """Config path for this instance (ECHOMIND_CONFIG wins, then data dir default)."""
    explicit = os.getenv("ECHOMIND_CONFIG", "").strip()
    if explicit:
        return Path(explicit)
    return Path(os.getenv("ECHOMIND_DATA_DIR", "data")) / "config.json"


def _instance_db_path() -> Path:
    """Per-instance SQLite file so two bots never share personality/memory."""
    explicit = os.getenv("ECHOMIND_DATA_DIR", "").strip()
    return Path(explicit or "data") / "echomind.db"


def build_live_asgi_app() -> FastAPI:
    """ASGI factory for uvicorn launching both Web Console and NapCat WS loop."""
    cfg_path = _instance_config_path()
    cfg = load_config_from_json(cfg_path) if cfg_path.exists() else AppConfig()
    holder: dict[str, EchoMindContainer] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = await EchoMindContainer.create(
            db_path=_instance_db_path(),
            operator_ids=cfg.operator_ids,
            default_chat_key=f"group:{cfg.allowed_groups[0]}"
            if cfg.allowed_groups
            else "group:10002002",
        )
        holder["c"] = container
        sub_app = create_web_app(container, config_path=cfg_path, auth_key=cfg.auth_key)
        app.router.routes.extend(sub_app.routes)
        live_rt = _build_live_runtime(cfg, container)
        await SkillConfigService(container).sync_states()
        stop_ev = asyncio.Event()
        ws_task = asyncio.create_task(live_rt.run_ws_forever(stop_ev))
        try:
            yield
        finally:
            stop_ev.set()
            ws_task.cancel()

    app = FastAPI(title="EchoMind Production Server", lifespan=lifespan)
    # 外层 app 拷贝了内层路由，中间件不会继承，需要显式再装一次
    app.middleware("http")(
        build_guard_and_cache_middleware(
            cfg.auth_key, lambda: getattr(holder.get("c"), "db", None)
        )
    )
    return app
