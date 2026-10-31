"""P4b: record what active traits would allow; never changes behavior."""

from __future__ import annotations

import logging
import time

from echomind.domain.models import TurnOutcome
from echomind.domain.trait_evidence_ports import ITraitEvidenceStore
from echomind.domain.trait_shadow_ports import IActiveTraitReader, ITraitShadowStore
from echomind.domain.trait_shadow_record import TraitShadowRecord
from echomind.mind.trait_action_eligibility import evaluate_eligibility

LOGGER = logging.getLogger(__name__)


class TraitShadowService:
    def __init__(
        self, reader: IActiveTraitReader, evidence: ITraitEvidenceStore,
        store: ITraitShadowStore,
    ) -> None:
        self._reader = reader
        self._evidence = evidence
        self._store = store

    async def record(self, outcome: TurnOutcome) -> None:
        try:
            traits = await self._reader.active_traits()
            evidence = {
                trait.trait_id: await self._evidence.list_trait_evidence(trait.trait_id, 200)
                for trait in traits
            }
            eligible = evaluate_eligibility(traits, evidence)
            await self._store.record_shadow(TraitShadowRecord(
                chat_key=outcome.chat_key, session_id=outcome.session_id,
                trait_ids=tuple(trait.trait_id for trait in traits),
                allowed_tools=tuple(sorted(eligible.allowed_tools)),
                allow_refusal=eligible.allow_refusal,
                actual_tools=tuple(outcome.tools_used),
                sent_count=len(outcome.sent_texts),
                created_ms=int(time.time() * 1000),
            ))
        except Exception:  # noqa: BLE001 - shadow telemetry must never break a turn
            LOGGER.warning("trait shadow record failed", exc_info=True)
