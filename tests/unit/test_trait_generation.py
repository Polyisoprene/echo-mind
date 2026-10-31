"""P2: quote-grounded trait generation, with no live prompt changes."""

from __future__ import annotations

import json
from typing import Any

from echomind.domain.trait_evidence import TraitEvidence
from echomind.mind.trait_generation import TraitTextGenerator


class FakeLlm:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls = 0

    async def complete(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return {"choices": [{"message": {"content": json.dumps(self.payload)}}]}


def _evidence(context: str, quote: str, eid: int) -> TraitEvidence:
    return TraitEvidence(
        evidence_id=eid, trait_id=1, session_id=f"s{eid}", turn_id=f"t{eid}",
        quote=quote, quote_kind="assistant", polarity=1,
        context_hash=context, created_ms=eid,
    )


async def test_two_contexts_generate_quote_grounded_candidate() -> None:
    llm = FakeLlm({
        "category": "habit",
        "trait_text": "看到图会先找画面里的小细节",
        "signature": {
            "situation": "看到图", "behavior": "先找小细节",
            "result": "会停下来看",
        },
        "evidence_quotes": ["喜欢看猫图"],
    })
    evidence = (
        _evidence("c1", "我今天喜欢看猫图", 1),
        _evidence("c2", "看到猫图又停下来看", 2),
    )
    candidate = await TraitTextGenerator(llm, "test-model").generate(1, evidence)
    assert candidate is not None
    assert candidate.status == "candidate"
    assert candidate.category == "habit"
    assert candidate.generator_model == "test-model"


async def test_fabricated_quote_is_rejected() -> None:
    llm = FakeLlm({
        "category": "habit",
        "trait_text": "喜欢猫",
        "signature": {
            "situation": "看到图", "behavior": "看猫",
            "result": "停下来",
        },
        "evidence_quotes": ["这句不在证据里"],
    })
    evidence = (
        _evidence("c1", "我今天喜欢看猫图", 1),
        _evidence("c2", "看到猫图又停下来看", 2),
    )
    candidate = await TraitTextGenerator(llm).generate(1, evidence)
    assert candidate is not None
    assert candidate.status == "rejected"
    assert "quote not found" in candidate.reject_reason


async def test_one_context_does_not_call_llm() -> None:
    llm = FakeLlm({"category": "habit", "trait_text": "猫", "evidence_quotes": ["猫"]})
    evidence = (_evidence("c1", "猫", 1),)
    assert await TraitTextGenerator(llm).generate(1, evidence) is None
    assert llm.calls == 0


async def test_tool_only_evidence_cannot_generate_prose() -> None:
    llm = FakeLlm({
        "category": "habit", "trait_text": "查看图片",
        "signature": {
            "situation": "看图", "behavior": "查看",
            "result": "确认",
        },
        "evidence_quotes": ["look_at_image"],
    })
    evidence = (
        TraitEvidence(
            evidence_id=1, trait_id=1, session_id="s1", turn_id="t1",
            quote="look_at_image", quote_kind="tool", polarity=1,
            context_hash="c1", created_ms=1,
        ),
        TraitEvidence(
            evidence_id=2, trait_id=1, session_id="s2", turn_id="t2",
            quote="look_at_image", quote_kind="tool", polarity=1,
            context_hash="c2", created_ms=2,
        ),
    )
    assert await TraitTextGenerator(llm).generate(1, evidence) is None
    assert llm.calls == 0


async def test_missing_signature_is_rejected() -> None:
    llm = FakeLlm({
        "category": "habit", "trait_text": "会看细节",
        "evidence_quotes": ["喜欢看猫图"],
    })
    evidence = (
        _evidence("c1", "喜欢看猫图", 1),
        _evidence("c2", "看到猫图又停下来看", 2),
    )
    candidate = await TraitTextGenerator(llm).generate(1, evidence)
    assert candidate is not None
    assert candidate.status == "rejected"
    assert "situation" in candidate.reject_reason
