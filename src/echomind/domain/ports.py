"""Role-Segregated Port Protocols (ISP & DIP) and Microkernel Extension Slot Contracts."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from echomind.domain.bond_stats import BondDepthStats
from echomind.domain.memory_ports import (
    IEmbeddingGateway as IEmbeddingGateway,
    IMemoryVectorStore as IMemoryVectorStore,
)
from echomind.domain.models import (
    AffectiveVector,
    AttentionDecision,
    CognitiveFrame,
    DriveState,
    EpisodicCard,
    Percept,
    PersonaTrait,
    PlasticParamSpec,
    ProactiveProposal,
    ProceduralRule,
    SemanticFact,
    SkillConfigField,
    SocialBondProfile,
    TurnOutcome,
    TurnRecord,
    WorkingSnapshot,
)
from echomind.domain.ports_media import (
    IBiliClient as IBiliClient,
    ICaptionGateway as ICaptionGateway,
    IMessageSender as IMessageSender,
    IOneBotApiCaller as IOneBotApiCaller,
    IQQMediaGateway as IQQMediaGateway,
    ISongCoverBackend as ISongCoverBackend,
    IVisionDescriber as IVisionDescriber,
    IVoiceBackend as IVoiceBackend,
)


@runtime_checkable
class IMemoryReader(Protocol):
    """Read-only segregated port for querying the 5-dimensional memory store (<=5 methods)."""

    async def get_episodic_cards(self, chat_key: str) -> tuple[EpisodicCard, ...]: ...

    async def get_semantic_facts(
        self,
        chat_key: str,
        min_confidence: float = 0.0,
        person_ids: tuple[str, ...] = (),
    ) -> tuple[SemanticFact, ...]: ...

    async def get_procedural_rules(self, chat_key: str) -> tuple[ProceduralRule, ...]: ...

    async def get_social_bond(self, chat_key: str, user_id: str) -> SocialBondProfile | None: ...

    async def get_rival_names(self, chat_key: str) -> tuple[str, ...]: ...


class IDisclosureLog(Protocol):
    """Audit trail for what she kept or said, and who already knows a memory."""

    async def log_disclosure(
        self, *, memory_kind: str, memory_id: int, venue: str,
        audience: tuple[str, ...], action: str, reason: str,
        phase: str = "gate", persona_json: str = "{}",
    ) -> None: ...

    async def mark_known(
        self, memory_kind: str, memory_id: int, person_id: str,
        state: str, confidence: float = 1.0,
    ) -> None: ...

    async def who_knows(
        self, memory_kind: str, memory_id: int
    ) -> tuple[tuple[str, str], ...]: ...

    async def has_grant(
        self, *, memory_kind: str, memory_id: int, grantee_id: str,
        now_ms: int | None = None,
    ) -> bool: ...


@runtime_checkable
class IMemoryWriter(Protocol):
    """Write-only segregated port for memory consolidation and reinforcement (<=5 methods)."""

    async def save_episodic_card(self, card: EpisodicCard) -> int: ...

    async def reinforce_episodic_card(self, card_id: int, recalled_ms: int) -> None: ...

    async def upsert_semantic_fact(self, fact: SemanticFact) -> tuple[bool, str]: ...

    async def upsert_procedural_rule(self, rule: ProceduralRule) -> int: ...

    async def upsert_social_bond(self, bond: SocialBondProfile) -> None: ...


@runtime_checkable
class IWorkingStateStore(Protocol):
    """Port for prefrontal working memory and self-tuning neuroplastic parameters (<=5 methods)."""

    async def load_working_state(self, scope_key: str) -> WorkingSnapshot: ...

    async def save_working_state(self, snapshot: WorkingSnapshot) -> None: ...

    async def get_plastic_params(self) -> dict[str, PlasticParamSpec]: ...

    async def update_plastic_param(
        self, key: str, delta: float, reason: str, reward: float
    ) -> PlasticParamSpec: ...

    async def sync_persona_traits(
        self, new_trait: PersonaTrait | None = None, strength_delta: int = 0,
        *, chat_key: str = "", source: str = "",
        decay_categories: tuple[str, ...] = (),
    ) -> tuple[PersonaTrait, ...]: ...


@runtime_checkable
class IGroupRosterReader(Protocol):
    """Segregated port for authoritative QQ group member & role lookup (<=5 methods)."""

    async def get_group_members(self, group_id: str) -> tuple[SocialBondProfile, ...]: ...


@runtime_checkable
class ILlmGateway(Protocol):
    """Port for high-availability LLM inference with automatic failover (<=5 methods)."""

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.6,
        max_tokens: int = 800,
        thinking_off: bool = False,
        *,
        chat_key: str = "",
        json_mode: bool = False,
        model_override: str = "",
    ) -> dict[str, Any]: ...


@runtime_checkable
class ICognitiveCoreFacade(Protocol):
    """Single Facade exposed by the Cognitive Core to the Runtime Layer (Law of Demeter)."""

    async def evaluate_incoming(
        self, percept: Percept, *, dry_run: bool = False
    ) -> AttentionDecision: ...

    async def build_cognitive_frame(
        self, chat_key: str, triggers: tuple[Percept, ...], *, dry_run: bool = False
    ) -> CognitiveFrame: ...

    async def on_turn_completed(self, outcome: TurnOutcome) -> None: ...

    async def run_autonomous_tick(self, now_ms: int) -> ProactiveProposal | None: ...

    async def consolidate_dialogue_batch(
        self,
        chat_key: str,
        transcript_lines: tuple[str, ...],
        llm: ILlmGateway,
        *,
        role_text: str = "",
    ) -> int: ...


# ── Five Microkernel Extension Slot Protocols (Open/Closed Principle) ──────


@runtime_checkable
class IPerceptEnricher(Protocol):
    """Slot 1: Perceptual input enrichment extension slot."""

    async def enrich(self, percept: Percept) -> Percept: ...


@runtime_checkable
class IToolExtension(Protocol):
    """Slot 2: Stateless effector tool extension slot."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def category(self) -> str: ...

    def parameters_schema(self) -> dict[str, Any]: ...

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str: ...


@runtime_checkable
class ICognitiveFacet(Protocol):
    """Slot 3: Inner cognitive dimension extension slot."""

    @property
    def facet_id(self) -> str: ...

    async def render_prompt_line(self, chat_key: str) -> str: ...


@runtime_checkable
class IProactiveProposer(Protocol):
    """Slot 4: Arbitrated proactive drive proposal extension slot (no raw timers!)."""

    async def propose(
        self, chat_key: str, affect: AffectiveVector, drives: DriveState
    ) -> ProactiveProposal | None: ...


@runtime_checkable
class IInspectorPanel(Protocol):
    """Slot 5: Declarative observability dashboard panel extension slot."""

    @property
    def panel_id(self) -> str: ...

    @property
    def panel_title(self) -> str: ...

    async def build_panel_data(self) -> dict[str, Any]: ...


@runtime_checkable
class IPersonaConstraintStore(Protocol):
    """Narrow port persisting owner-imposed phrase bans for self-correction."""

    async def get_banned_phrases(self) -> tuple[str, ...]: ...

    async def add_banned_phrase(self, phrase: str, reason: str) -> None: ...


@runtime_checkable
class ITurnTraceStore(Protocol):
    """Narrow port persisting per-turn execution traces (LLM + tool steps)."""

    async def save_turn(self, record: TurnRecord) -> None: ...

    async def list_turns(self, chat_key: str, limit: int = 40) -> tuple[TurnRecord, ...]: ...


@runtime_checkable
class IBondDepthStore(Protocol):
    """Narrow port persisting per-member interaction counters for earned bond depth."""

    async def upsert_stats(self, stats: BondDepthStats) -> None: ...
    async def add_impact(
        self, chat_key: str, user_id: str, magnitude: float, *, betray: bool = False
    ) -> None: ...
    async def get_stats(self, chat_key: str, user_id: str) -> BondDepthStats | None: ...
    async def set_bond_depth(self, chat_key: str, user_id: str, depth: float) -> None: ...
    async def top_stats(self, limit: int = 50) -> tuple[BondDepthStats, ...]: ...


@runtime_checkable
class IConfigurableTool(Protocol):
    """Optional slot-2 mixin: a tool that exposes operator-editable settings."""

    def config_fields(self) -> tuple[SkillConfigField, ...]: ...


@runtime_checkable
class ISkillConfigStore(Protocol):
    """Narrow port persisting per-skill configuration values."""

    async def get_skill_config(self, skill: str) -> dict[str, str]: ...
    async def set_skill_config(self, skill: str, values: dict[str, str]) -> None: ...


@runtime_checkable
class IPersonaLayerStore(Protocol):
    """Fast persona state offsets and the daily observation buffer (<=5 methods)."""

    async def load_state(self) -> dict[str, tuple[float, int]]: ...

    async def save_state(self, key: str, offset: float, now_ms: int) -> None: ...

    async def record_observation(self, key: str, delta: float, now_ms: int) -> None: ...

    async def pop_observations(self, now_ms: int) -> dict[str, tuple[float, int]]:
        """Return {key: (total, last_settled_ms)} and mark these keys as settled."""
        ...


@runtime_checkable
class IAsyncSqlStore(Protocol):
    """Narrow port for async SQLite connection context management (DIP for runtime)."""

    def connect(self) -> Any: ...
