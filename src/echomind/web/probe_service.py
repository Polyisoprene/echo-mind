"""Cognitive probe: run a synthetic message through the 12-layer core without sending."""

from __future__ import annotations

import time
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept


class CognitiveProbeService:
    """Let the operator inspect exactly what the LLM will be told for a message."""

    def __init__(self, container: EchoMindContainer) -> None:
        self._c = container

    async def probe(
        self, chat_key: str, text: str, sender_id: str = "", sender_name: str = ""
    ) -> dict[str, Any]:
        """Build a cognitive frame for a synthetic percept and return the rendered block."""
        target = chat_key or self._c.default_chat_key
        uid = sender_id or "probe"
        percept = Percept(
            chat_key=target,
            scene="private" if "private:" in target else "group",
            message_id=f"probe_{int(time.time() * 1000)}",
            timestamp_ms=int(time.time() * 1000),
            sender_id=uid,
            sender_name=sender_name or uid,
            text=text,
            is_at_me=True,
        )
        decision = await self._c.cognitive_facade.evaluate_incoming(percept, dry_run=True)
        frame = await self._c.cognitive_facade.build_cognitive_frame(
            target, (percept,), dry_run=True
        )
        return {
            "ok": True,
            "attention": decision.model_dump(),
            "scene": frame.scene,
            "must_reply": frame.must_reply,
            "affect": frame.affect.model_dump(),
            "drives": frame.drives.model_dump(),
            "cybernetic_core": frame.cybernetic_core.model_dump(),
            "banned_phrases": list(frame.banned_phrases),
            "epistemic_warnings": list(frame.epistemic_warnings),
            "curiosity_prompts": list(frame.curiosity_prompts),
            "rendered_mind_block": frame.rendered_mind_block,
        }
