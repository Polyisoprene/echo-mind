"""P2: generate a trait candidate from evidence quotes (offline/shadow)."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, cast

from echomind.domain.ports import ILlmGateway
from echomind.domain.trait_candidate import TraitCandidate
from echomind.domain.trait_evidence import TraitEvidence

_CATEGORIES = frozenset({"habit", "temperament", "taste", "taboo"})


def _extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message")
    body = message if isinstance(message, dict) else {}
    return str(body.get("content") or "").strip()


def _parse_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:]).removesuffix("```").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _prompt(evidence: tuple[TraitEvidence, ...]) -> str:
    lines = "\n".join(
        f"- [{item.evidence_id}] {item.quote}" for item in evidence
    )
    return (
        "你是人格证据归纳器。只根据下列证据，提出一条候选特质。\n"
        "要求：\n"
        "1. category 只能是 habit/temperament/taste/taboo；\n"
        "2. trait_text 用一句中文描述她在什么情境下倾向怎么做；\n"
        "3. evidence_quotes 至少 1 条，必须逐字出现在证据里；\n"
        "4. 不要编造证据，不要引用隐私细节。\n"
        '只输出 JSON：{"category":"...","trait_text":"...","evidence_quotes":["..."]}\n'
        f"证据：\n{lines}"
    )


def _digest(evidence: tuple[TraitEvidence, ...]) -> str:
    raw = "|".join(sorted(f"{item.evidence_id}:{item.quote}" for item in evidence))
    return hashlib.sha256(raw.encode()).hexdigest()


def _evidence_json(evidence: tuple[TraitEvidence, ...]) -> str:
    return json.dumps(
        [{"id": item.evidence_id, "quote": item.quote} for item in evidence],
        ensure_ascii=False,
    )


def _validate(
    payload: dict[str, Any] | None, evidence: tuple[TraitEvidence, ...]
) -> str | None:
    if payload is None:
        return "invalid JSON"
    reason = _validate_text(payload)
    if reason is not None:
        return reason
    return _validate_quotes(payload, evidence)


def _validate_text(payload: dict[str, Any]) -> str | None:
    category = payload.get("category")
    text = payload.get("trait_text")
    if category not in _CATEGORIES or not isinstance(text, str) or not text.strip():
        return "invalid category/text"
    return None


def _validate_quotes(
    payload: dict[str, Any], evidence: tuple[TraitEvidence, ...]
) -> str | None:
    quotes = payload.get("evidence_quotes")
    if not isinstance(quotes, list) or not quotes or not all(
        isinstance(item, str) and item for item in quotes
    ):
        return "missing evidence_quotes"
    sources = [item.quote for item in evidence]
    if any(not any(quote in source for source in sources) for quote in quotes):
        return "quote not found in evidence"
    return None


class TraitTextGenerator:
    """Generate candidates without touching the live prompt."""

    def __init__(self, llm: ILlmGateway, model_name: str = "") -> None:
        self._llm = llm
        self._model = model_name

    async def generate(
        self, trait_id: int, evidence: tuple[TraitEvidence, ...]
    ) -> TraitCandidate | None:
        contexts = {item.context_hash for item in evidence if item.polarity > 0}
        if len(contexts) < 2:
            return None
        if not any(item.quote_kind != "tool" for item in evidence):
            return None
        response = await self._llm.complete(
            [{"role": "user", "content": _prompt(evidence)}],
            temperature=0.0, json_mode=True,
        )
        payload = _parse_json(_extract_text(response))
        now_ms = int(time.time() * 1000)
        digest = _digest(evidence)
        evidence_json = _evidence_json(evidence)
        reason = _validate(payload, evidence)
        if reason is not None:
            return self._reject(trait_id, reason, digest, evidence_json, now_ms)
        assert payload is not None
        return TraitCandidate(
            trait_id=trait_id, category=cast(Any, str(payload["category"])),
            trait_text=str(payload["trait_text"]).strip(),
            evidence_json=evidence_json, prompt_hash=digest,
            generator_model=self._model, status="candidate", created_ms=now_ms,
        )

    def _reject(
        self, trait_id: int, reason: str, digest: str,
        evidence_json: str, now_ms: int,
    ) -> TraitCandidate:
        return TraitCandidate(
            trait_id=trait_id, category="habit", trait_text="(rejected)",
            evidence_json=evidence_json, prompt_hash=digest,
            generator_model=self._model, status="rejected",
            reject_reason=reason, created_ms=now_ms,
        )
