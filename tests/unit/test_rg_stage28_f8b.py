"""Stage 28 RGR-F8b: one failing enricher must never drop the whole inbound message."""

from __future__ import annotations

from echomind.adapters.onebot.enrichers import PerceptEnrichmentPipeline
from echomind.domain.models import Percept


class _BoomEnricher:
    async def enrich(self, percept: Percept) -> Percept:
        raise AttributeError("gateway missing describe_image")


class _TagEnricher:
    async def enrich(self, percept: Percept) -> Percept:
        return percept.model_copy(update={"text": percept.text + " [tagged]"})


def _percept() -> Percept:
    return Percept(
        chat_key="group:10002002", scene="group", message_id="f8b", timestamp_ms=1_700_000_000_000,
        sender_id="2005", sender_name="冰色", text="图呢",
    )


async def test_rg_f8b_enricher_failure_keeps_message() -> None:
    """A raising enricher is isolated: the message survives and later enrichers still run."""
    pipeline = PerceptEnrichmentPipeline((_BoomEnricher(), _TagEnricher()))
    out = await pipeline.process(_percept())
    assert out.text.endswith("[tagged]"), "pipeline must keep going after an enricher failure"
