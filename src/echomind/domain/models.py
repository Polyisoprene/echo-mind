"""Immutable Domain Value Objects (Frozen DTOs) enforcing Law of Demeter & Type Safety."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenValueObject(BaseModel):
    """Base class for all immutable cross-layer value objects."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class MediaAttachment(FrozenValueObject):
    """Normalized multimodal attachment (image, GIF 2x2 storyboard, video frames, voice)."""

    kind: Literal["image", "gif_storyboard", "video_frames", "voice", "forward"]
    url: str = ""
    local_path: str = ""
    data_url: str = ""
    description: str = ""
    message_id: str = ""


class Percept(FrozenValueObject):
    """Normalized perceptual event entering the Cognitive Core."""

    chat_key: str
    scene: Literal["group", "private"]
    message_id: str
    timestamp_ms: int
    sender_id: str
    sender_name: str
    sender_role: Literal["owner", "admin", "member", "self"] = "member"
    text: str
    is_at_me: bool = False
    is_called_by_name: bool = False
    is_quoted_me: bool = False
    is_poke_me: bool = False
    quoted_message_id: str = ""
    quoted_text: str = ""
    media: tuple[MediaAttachment, ...] = ()


class AttentionDecision(FrozenValueObject):
    """Output of the Perceptual & Salience Gate."""

    should_wake: bool
    salience_score: float = Field(ge=0.0, le=1.0)
    tier: int = Field(ge=0, le=4)
    reason: str
    detected_unknown_terms: tuple[str, ...] = ()
    has_unseen_media: bool = False


class AffectiveVector(FrozenValueObject):
    """Continuous emotional state with natural half-life decay & CPM irritation."""

    valence: float = Field(default=20.0, ge=-100.0, le=100.0)
    energy: float = Field(default=85.0, ge=0.0, le=100.0)
    jealousy: float = Field(default=0.0, ge=0.0, le=100.0)
    shyness: float = Field(default=10.0, ge=0.0, le=100.0)
    irritation: float = Field(default=0.0, ge=0.0, le=100.0)


class DriveState(FrozenValueObject):
    """Four intrinsic drives powering autonomous exploration and proactive behavior."""

    curiosity: float = Field(default=40.0, ge=0.0, le=100.0)
    attachment: float = Field(default=75.0, ge=0.0, le=100.0)
    jealousy_drive: float = Field(default=0.0, ge=0.0, le=100.0)
    social_expression: float = Field(default=35.0, ge=0.0, le=100.0)


class IntentionItem(FrozenValueObject):
    """Short-term working memory intention / unfinished thought."""

    summary: str
    created_at_ms: int
    expires_at_ms: int
    target_user_id: str = ""


class WorkingSnapshot(FrozenValueObject):
    """Encapsulated prefrontal working memory snapshot (Parameter Object pattern)."""

    scope_key: str
    affect: AffectiveVector = AffectiveVector()
    drives: DriveState = DriveState()
    current_activity: str = ""
    inner_thought: str = ""
    intentions: tuple[IntentionItem, ...] = ()
    curiosity_queue: tuple[str, ...] = ()


class TheoryOfMindFrame(FrozenValueObject):
    """Inferred mental state and subtext of the interlocutor."""

    target_user_id: str
    inferred_mood: str
    inferred_intent: str
    is_teasing_or_baiting: bool = False


class EpisodicCard(FrozenValueObject):
    """Hippocampal consolidated event memory card with key detail anchor."""

    card_id: int = 0
    chat_key: str
    timestamp_ms: int
    msg_seq: int = 0
    summary: str
    key_detail: str = ""
    participants: tuple[str, ...] = ()
    importance: float = Field(default=3.0, ge=1.0, le=5.0)
    pinned: bool = False
    rehearsals: int = Field(default=0, ge=0)
    last_recalled_ms: int = 0


class RecalledMemoryItem(FrozenValueObject):
    """Episodic card decorated with real-time Ebbinghaus retention & clarity tier."""

    card: EpisodicCard
    retention: float = Field(ge=0.0, le=1.0)
    clarity: Literal["clear", "fuzzy"]


class SemanticFact(FrozenValueObject):
    """Epistemic fact with calibrated confidence, provenance, and anti-spoofing lock."""

    fact_id: int = 0
    chat_key: str
    subject: str
    fact_text: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    is_locked: bool = False
    source: Literal["system", "owner", "explored", "peer"] = "peer"
    revision_count: int = 1


class ProceduralRule(FrozenValueObject):
    """Conditioned reflex / interactive habit rule."""

    rule_id: int = 0
    chat_key: str
    trigger_keyword: str
    trigger_user_id: str = ""
    action_instruction: str
    strength: int = Field(default=3, ge=1, le=10)


class SocialBondProfile(FrozenValueObject):
    """Unified social bond, affinity, traits, and epistemic trust score for a member."""

    chat_key: str
    user_id: str
    user_name: str
    group_role: Literal["owner", "admin", "member"] = "member"
    affinity_score: float = 0.0
    affinity_level: int = Field(default=1, ge=0, le=5)
    msg_count: int = 0
    trust_score: float = Field(default=0.8, ge=0.0, le=1.0)
    is_rival: bool = False
    rival_reason: str = ""
    traits: tuple[str, ...] = ()


class PersonaTrait(FrozenValueObject):
    """Dynamically grown personality habit, quirk, or preference."""

    trait_id: int = 0
    category: Literal["habit", "temperament", "taste", "taboo"] = "habit"
    trait_text: str
    strength: int = Field(default=5, ge=0, le=10)


class PlasticParamSpec(FrozenValueObject):
    """Neuroplastic self-tuning control parameter with homeostatic bounds."""

    key: str
    value: float
    min_bound: float
    max_bound: float
    description: str = ""


class ProactiveProposal(FrozenValueObject):
    """Arbitrated proposal for autonomous exploration or proactive speaking."""

    chat_key: str
    drive_kind: Literal[
        "curiosity_explore",
        "bili_surf",
        "attachment_private",
        "jealousy_poke",
        "cold_group_topic",
    ]
    priority: float = Field(ge=0.0, le=100.0)
    goal_instruction: str
    topic_hint: str = ""


class CyberneticCoreState(FrozenValueObject):
    """Haken Order Parameters (3 master magnetic needles) & Ashby selected reagents."""

    stance_order: float = Field(default=0.2, ge=-1.0, le=1.0)
    epistemic_order: float = Field(default=0.3, ge=0.0, le=1.0)
    modality_order: float = Field(default=0.2, ge=0.0, le=1.0)
    core_regime: str = "日常共鸣态"
    active_reagents: tuple[str, ...] = ("日常轻装剂",)
    selected_tools: tuple[str, ...] = ()
    recommended_temperature: float = Field(default=0.65, ge=0.1, le=1.2)


class CognitiveFrame(FrozenValueObject):
    """Complete immutable cognitive state frame delivered to the Runtime Prompt Composer."""

    chat_key: str
    scene: Literal["group", "private"]
    must_reply: bool
    affect: AffectiveVector
    drives: DriveState
    rendered_mind_block: str
    epistemic_warnings: tuple[str, ...] = ()
    curiosity_prompts: tuple[str, ...] = ()
    banned_phrases: tuple[str, ...] = ()
    cybernetic_core: CyberneticCoreState = Field(default_factory=CyberneticCoreState)


class SkillConfigField(FrozenValueObject):
    """Declarative description of one configurable field a skill exposes."""

    key: str
    label: str
    kind: Literal["text", "password", "number", "boolean"] = "text"
    default: str = ""
    placeholder: str = ""
    required: bool = False
    secret: bool = False
    help: str = ""


class TurnStep(FrozenValueObject):
    """One observable step inside a cognitive turn: an LLM call or a tool call."""

    seq: int = 0
    kind: Literal["llm", "tool"] = "llm"
    name: str = ""
    detail: str = ""
    output: str = ""
    elapsed_ms: int = 0


class TurnRecord(FrozenValueObject):
    """Persisted per-turn execution trace for the console timeline."""

    turn_id: str
    chat_key: str
    ts: int
    trigger: str = ""
    status: str = "done"
    rounds: int = 0
    sent_count: int = 0
    total_ms: int = 0
    model: str = ""
    context_count: int = 0
    trigger_count: int = 0
    system_prompt: str = ""
    user_prompt: str = ""
    steps: tuple[TurnStep, ...] = ()


class TurnOutcome(FrozenValueObject):
    """Post-turn telemetry fed back into Hippocampus and Neuroplasticity Engine."""

    session_id: str
    chat_key: str
    triggers: tuple[Percept, ...]
    sent_texts: tuple[str, ...] = ()
    tools_used: tuple[str, ...] = ()
    social_reward: float = Field(default=0.0, ge=-1.0, le=1.0)
    epistemic_conflict_detected: bool = False
    steps: tuple[TurnStep, ...] = ()
    total_ms: int = 0
    status: str = "done"
    context_count: int = 0
    system_prompt: str = ""
    user_prompt: str = ""
