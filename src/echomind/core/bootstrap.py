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
from echomind.adapters.storage.disclosure_repo import SqliteDisclosureLog
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.person_level_repo import load_bonds, load_stats
from echomind.adapters.storage.person_store import SqlitePersonStore
from echomind.adapters.storage.persona_layer_repo import SqlitePersonaLayerStore
from echomind.adapters.storage.skill_config_repo import SqliteSkillConfigStore
from echomind.adapters.storage.trace_repo import SqliteTurnTraceStore
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.core.events import AsyncEventBus
from echomind.domain.models import TurnOutcome
from echomind.domain.ports import IOneBotApiCaller
from echomind.extensions.registry import ExtensionRegistry
from echomind.mind.facade import CognitiveCoreFacade
from echomind.mind.naming import BotNaming, set_bot_naming
from echomind.mind.person_level_service import PersonLevelService
from echomind.mind.trait_shadow_service import TraitShadowService
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


async def _open_db(path: Path) -> SqliteDatabase:
    db = SqliteDatabase(path)
    await db.initialize()
    return db


def _build_trait_shadow(db: SqliteDatabase) -> TraitShadowService:
    store = SqliteTraitShadowStore(db)
    return TraitShadowService(store, SqliteTraitEvidenceStore(db), store)


async def _run_backfill(bond_store: SqliteBondDepthStore) -> None:
    if await bond_store.needs_backfill():
        await bond_store.backfill_from_history()


def _build_person_services(db: SqliteDatabase) -> tuple[PersonLevelService, SqliteDisclosureLog]:
    store = SqlitePersonStore(db)
    service = PersonLevelService(
        bonds=lambda: load_bonds(db), stats=lambda: load_stats(db),
        persist=store.save, load=store.load_with_ts,
    )
    return service, SqliteDisclosureLog(db)


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
        self.persona_layers: SqlitePersonaLayerStore | None = None
        self.person_level: Any = None
        self.onebot_runtime: Any = None

    @classmethod
    async def create(
        cls,
        db_path: Path,
        default_chat_key: str = "group:10002002",
        operator_ids: tuple[str, ...] = (),
    ) -> EchoMindContainer:
        """Initialize SQLite WAL schema, default 7D plastic params, and core extensions."""
        db = await _open_db(db_path)
        mem_repo = SqliteMemoryRepository(db)
        work_store = SqliteWorkingStateStore(db)
        trace_store, skill_store = SqliteTurnTraceStore(db), SqliteSkillConfigStore(db)
        await work_store.ensure_default_params()
        set_bot_naming(BotNaming())
        bond_store = SqliteBondDepthStore(db)
        await bond_store.ensure_schema()
        layers = await SqlitePersonaLayerStore.open(db)
        await _run_backfill(bond_store)
        person_level, disclosure_log = _build_person_services(db)
        facade = CognitiveCoreFacade(
            mem_reader=mem_repo, mem_writer=mem_repo, working_store=work_store,
            default_group_key=default_chat_key,
            constraint_store=work_store, trace_store=trace_store, bond_store=bond_store,
            operator_ids=operator_ids, persona_layers=layers,
            person_level=person_level, disclosure_log=disclosure_log,
            trait_evidence_store=SqliteTraitEvidenceStore(db),
            trait_shadow=_build_trait_shadow(db),
            trait_links=SqliteTraitMemoryLinkStore(db), turn_linker=SqliteTraitMemoryLinkStore(db),
        )
        instance = cls(
            db=db, memory_repo=mem_repo, working_store=work_store,
            cognitive_facade=facade, registry=_build_registry(db),
            trace_store=trace_store, skill_config_store=skill_store,
            default_chat_key=default_chat_key,
        )
        instance.bond_depth_store, instance.persona_layers = bond_store, layers
        async def _on_turn_completed(_outcome: TurnOutcome) -> None:
            instance.published_turns += 1

        instance.event_bus.subscribe(TurnOutcome, _on_turn_completed)
        return instance
