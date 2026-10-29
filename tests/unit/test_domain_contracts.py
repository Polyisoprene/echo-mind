"""Unit & Property-Based (Hypothesis) Tests for Domain Contracts & Immutability."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from echomind.domain.models import (
    AffectiveVector,
    AttentionDecision,
    CognitiveFrame,
    DriveState,
    EpisodicCard,
    IntentionItem,
    MediaAttachment,
    Percept,
    PlasticParamSpec,
    ProactiveProposal,
    ProceduralRule,
    RecalledMemoryItem,
    SemanticFact,
    SocialBondProfile,
    TheoryOfMindFrame,
    TurnOutcome,
)


def test_percept_is_strictly_immutable_and_forbids_extra_fields() -> None:
    att = MediaAttachment(kind="image", url="https://example.com/a.jpg")
    p = Percept(
        chat_key="group:10002002",
        scene="group",
        message_id="1001",
        timestamp_ms=1793160000000,
        sender_id="10001001",
        sender_name="L今晚早睡了吗",
        sender_role="member",
        text="回音在吗",
        is_called_by_name=True,
        media=(att,),
    )
    with pytest.raises(ValidationError):
        p.text = "tampered"

    with pytest.raises(ValidationError):
        Percept.model_validate(
            {
                "chat_key": "group:10002002",
                "scene": "group",
                "message_id": "1001",
                "timestamp_ms": 1,
                "sender_id": "1",
                "sender_name": "a",
                "text": "hi",
                "unknown_field": "bad",
            }
        )


@given(
    valence=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False),
    energy=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    jealousy=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    shyness=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
)
def test_affective_vector_property_bounds(
    valence: float, energy: float, jealousy: float, shyness: float
) -> None:
    vec = AffectiveVector(valence=valence, energy=energy, jealousy=jealousy, shyness=shyness)
    assert -100.0 <= vec.valence <= 100.0
    assert 0.0 <= vec.energy <= 100.0
    assert 0.0 <= vec.jealousy <= 100.0
    assert 0.0 <= vec.shyness <= 100.0


def test_all_domain_value_objects_instantiate_cleanly() -> None:
    dec = AttentionDecision(should_wake=True, salience_score=0.95, tier=1, reason="点名叫我")
    drives = DriveState(
        curiosity=65.0, attachment=80.0, jealousy_drive=10.0, social_expression=50.0
    )
    intent = IntentionItem(summary="等L叫我尾尾", created_at_ms=1, expires_at_ms=2)
    tom = TheoryOfMindFrame(
        target_user_id="10001001", inferred_mood="开心", inferred_intent="测试记忆"
    )
    card = EpisodicCard(
        chat_key="group:10002002", timestamp_ms=1, summary="测试事件总结", key_detail="细节锚点"
    )
    recalled = RecalledMemoryItem(card=card, retention=0.92, clarity="clear")
    fact = SemanticFact(
        chat_key="group:10002002",
        subject="群主",
        fact_text="馍馍(10004004)",
        confidence=1.0,
        is_locked=True,
        source="system",
    )
    rule = ProceduralRule(
        chat_key="private:10001001",
        trigger_keyword="尾尾",
        action_instruction="乖巧应声",
        strength=5,
    )
    bond = SocialBondProfile(
        chat_key="group:10002002",
        user_id="10001001",
        user_name="L",
        affinity_score=9999.0,
        affinity_level=5,
        trust_score=1.0,
    )
    param = PlasticParamSpec(key="skepticism", value=55.0, min_bound=10.0, max_bound=95.0)
    prop = ProactiveProposal(
        chat_key="group:10002002",
        drive_kind="curiosity_explore",
        priority=80.0,
        goal_instruction="搜新梗",
    )
    frame = CognitiveFrame(
        chat_key="group:10002002",
        scene="group",
        must_reply=True,
        affect=AffectiveVector(),
        drives=drives,
        rendered_mind_block="【🧠 认知核心状态】",
    )
    outcome = TurnOutcome(
        session_id="s1", chat_key="group:10002002", triggers=(), social_reward=0.5
    )

    assert dec.should_wake and intent.summary and tom.inferred_mood
    assert recalled.clarity == "clear" and fact.is_locked and rule.strength == 5
    assert bond.trust_score == 1.0 and param.value == 55.0 and prop.priority == 80.0
    assert frame.must_reply and outcome.social_reward == 0.5
