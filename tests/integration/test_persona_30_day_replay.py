"""30-day synthetic replay: streams change trait evidence, not one-turn noise."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.persona_layer_repo import SqlitePersonaLayerStore
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.persona_dynamics import TRAIT_MAX_DEVIATION
from echomind.mind.plasticity import PARAM_BASELINES, NeuroplasticityEngine

BASE = 1_700_000_000_000
DAY = 86_400_000
WARM_QUOTE = "我看到图里那个小槽点了"
OFFENSE_QUOTE = "别用命令语气使唤我"


def _outcome(day: int, *, warm: bool) -> TurnOutcome:
    event_ms = BASE + day * DAY
    percept = Percept(
        chat_key="g", scene="group", message_id=f"m{day}", timestamp_ms=event_ms,
        sender_id="u1", sender_name="U", text="发图" if warm else "命令",
    )
    return TurnOutcome(
        session_id=f"turn-{day}", chat_key="g", triggers=(percept,),
        sent_texts=(WARM_QUOTE if warm else OFFENSE_QUOTE,),
        tools_used=("look_at_image",) if warm else (),
        social_reward=0.8 if warm else -0.8,
    )


async def _run_stream(
    tmp_path: Path, name: str, *, mixed: bool = False,
) -> tuple[SqliteWorkingStateStore, SqliteTraitEvidenceStore]:
    db = SqliteDatabase(tmp_path / f"{name}.db")
    await db.initialize()
    working = SqliteWorkingStateStore(db)
    await working.ensure_default_params()
    layers = SqlitePersonaLayerStore(db)
    await layers.ensure_schema()
    evidence_store = SqliteTraitEvidenceStore(db)
    engine = NeuroplasticityEngine(working, layers, evidence_store=evidence_store)
    for day in range(1, 31):
        warm = (day % 2 == 0) if mixed else (name == "warm")
        event_ms = BASE + day * DAY
        await engine.adapt_from_outcome(_outcome(day, warm=warm), now_ms=event_ms)
        await engine.settle_baseline(event_ms + DAY)
    return working, evidence_store


async def test_warm_and_offense_streams_grow_different_active_traits(tmp_path: Path) -> None:
    warm_store, warm_evidence = await _run_stream(tmp_path, "warm")
    offense_store, offense_evidence = await _run_stream(tmp_path, "offense")
    warm = await warm_store.sync_persona_traits()
    offense = await offense_store.sync_persona_traits()
    warm_trait = next(t for t in warm if "看到群友发图" in t.trait_text)
    offense_trait = next(t for t in offense if "工具人" in t.trait_text)
    warm_rows = await warm_evidence.list_trait_evidence(warm_trait.trait_id, 100)
    offense_rows = await offense_evidence.list_trait_evidence(offense_trait.trait_id, 100)
    assert len({row.context_hash for row in warm_rows}) == 30
    assert len({row.context_hash for row in offense_rows}) == 30
    assert await warm_evidence.refresh_lifecycle(warm_trait.trait_id) == "active"
    assert await offense_evidence.refresh_lifecycle(offense_trait.trait_id) == "active"


async def test_30_day_drift_stays_within_persona_bound(tmp_path: Path) -> None:
    store, _ = await _run_stream(tmp_path, "mixed", mixed=True)
    params = await store.get_plastic_params()
    for key, spec in params.items():
        baseline = PARAM_BASELINES.get(key)
        if baseline is not None:
            assert abs(spec.value - baseline) <= TRAIT_MAX_DEVIATION + 1e-6, key
        assert spec.min_bound <= spec.value <= spec.max_bound, key
    traits = await store.sync_persona_traits()
    assert any("看到群友发图" in t.trait_text for t in traits)
    assert any("工具人" in t.trait_text for t in traits)
