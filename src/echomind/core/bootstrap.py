"""M5.1 Composition Root (Dependency Injection Container) wiring Adapters, Mind & Runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.media.feiyu import FeiyuVoiceBackend
from echomind.adapters.onebot.enrichers import (
    CardAndForwardEnricher,
    ImageCaptionCacheEnricher,
    QuoteStickerEnricher,
)
from echomind.adapters.storage.bond_depth_repo import SqliteBondDepthStore
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.skill_config_repo import SqliteSkillConfigStore
from echomind.adapters.storage.trace_repo import SqliteTurnTraceStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.core.events import AsyncEventBus
from echomind.domain.models import TurnOutcome
from echomind.domain.ports import IOneBotApiCaller
from echomind.extensions.registry import ExtensionRegistry
from echomind.mind.facade import CognitiveCoreFacade
from echomind.runtime.prompt_composer import PromptComposer
from echomind.tools.cnmeme_wiki import CnMemeWikiClient, CnMemeWikiTool
from echomind.tools.explore_and_voice import CompositeSearchBackend, HolyWebSearchTool


def _build_registry(db: SqliteDatabase) -> ExtensionRegistry:
    """Register the built-in enrichment sensors and stateless tools."""
    reg = ExtensionRegistry()
    reg.register_sensor(QuoteStickerEnricher(db))
    reg.register_sensor(CardAndForwardEnricher())
    reg.register_sensor(ImageCaptionCacheEnricher(db))
    meme_client = CnMemeWikiClient()
    reg.register_tool(CnMemeWikiTool(meme_client))
    reg.register_tool(HolyWebSearchTool(CompositeSearchBackend((meme_client,))))
    return reg


class EchoMindContainer:
    """Dependency Injection Container holding initialized singletons for the application."""

    def __init__(
        self,
        db: SqliteDatabase,
        memory_repo: SqliteMemoryRepository,
        working_store: SqliteWorkingStateStore,
        cognitive_facade: CognitiveCoreFacade,
        registry: ExtensionRegistry,
        *,
        trace_store: SqliteTurnTraceStore,
        skill_config_store: SqliteSkillConfigStore | None = None,
        default_chat_key: str = "group:10002002",
    ) -> None:
        self.db = db
        self.memory_repo = memory_repo
        self.working_store = working_store
        self.cognitive_facade = cognitive_facade
        self.registry = registry
        self.trace_store = trace_store
        self.default_chat_key = default_chat_key
        self.llm_gateway: FailoverLlmGateway | None = None
        self.voice_backend: FeiyuVoiceBackend | None = None
        self.vision_describer: Any = None
        self.prompt_composer: PromptComposer | None = None
        self.onebot_caller: IOneBotApiCaller | None = None
        self.scheduler: Any = None
        self.event_bus = AsyncEventBus()
        self.published_turns: int = 0
        self.skill_config_store: SqliteSkillConfigStore | None = skill_config_store
        self.bond_depth_store: SqliteBondDepthStore | None = None

    @classmethod
    async def create(
        cls,
        db_path: Path,
        owner_qq: str = "10001001",
        default_chat_key: str = "group:10002002",
    ) -> EchoMindContainer:
        """Initialize SQLite WAL schema, default 7D plastic params, and core extensions."""
        db = SqliteDatabase(db_path)
        await db.initialize()
        mem_repo = SqliteMemoryRepository(db)
        work_store = SqliteWorkingStateStore(db)
        trace_store = SqliteTurnTraceStore(db)
        skill_store = SqliteSkillConfigStore(db)
        await work_store.ensure_default_params()
        bond_store = SqliteBondDepthStore(db)
        await bond_store.ensure_schema()
        facade = CognitiveCoreFacade(
            mem_reader=mem_repo, mem_writer=mem_repo, working_store=work_store,
            owner_qq=owner_qq, default_group_key=default_chat_key,
            constraint_store=work_store, trace_store=trace_store,
        )
        instance = cls(
            db=db, memory_repo=mem_repo, working_store=work_store,
            cognitive_facade=facade, registry=_build_registry(db),
            trace_store=trace_store, skill_config_store=skill_store,
            default_chat_key=default_chat_key,
        )
        instance.bond_depth_store = bond_store

        async def _on_turn_completed(_outcome: TurnOutcome) -> None:
            instance.published_turns += 1

        instance.event_bus.subscribe(TurnOutcome, _on_turn_completed)
        return instance
