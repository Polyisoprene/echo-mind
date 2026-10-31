"""Trait memory links must be able to break a live-retriever tie."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import PersonaTrait, SemanticFact
from echomind.domain.trait_evidence import TraitEvidence
from echomind.domain.trait_memory_link import TraitMemoryLink
from echomind.mind.semantic_memory import SemanticMemoryRetriever


class _Store:
    def __init__(self, vectors: dict[int, tuple[float, ...]]) -> None:
        self._vectors = vectors

    async def get(
        self, memory_kind: str, memory_ids: tuple[int, ...], model: str = ""
    ) -> dict[int, tuple[float, ...]]:
        return {k: v for k, v in self._vectors.items() if k in memory_ids}


class _Embedder:
    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return ((1.0, 0.0),)


def _facts() -> tuple[SemanticFact, ...]:
    return (
        SemanticFact(fact_id=1, chat_key="g", subject="电影", fact_text="催泪",
                     confidence=0.5, is_locked=True, event_time_ms=1),
        SemanticFact(fact_id=2, chat_key="g", subject="猫", fact_text="猫粮",
                     confidence=0.9, event_time_ms=2),
    )


async def _retriever(db: SqliteDatabase, *, with_trait: bool) -> SemanticMemoryRetriever:
    links = SqliteTraitMemoryLinkStore(db)
    reader = SqliteTraitShadowStore(db)
    if not with_trait:
        return SemanticMemoryRetriever(
            _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)}), "m"
        )
    traits = await SqliteWorkingStateStore(db).sync_persona_traits(
        new_trait=PersonaTrait(category="habit", trait_text="猫相关", strength=6),
        chat_key="g", source="turn:t1",
    )
    trait = traits[0]
    evidence = SqliteTraitEvidenceStore(db)
    for index, context in enumerate(("c1", "c2"), 1):
        await evidence.record_trait_evidence(TraitEvidence(
            trait_id=trait.trait_id, session_id=f"s{index}", turn_id=f"t{index}",
            quote="猫粮", quote_kind="assistant", polarity=1,
            context_hash=context, created_ms=index,
        ))
    await evidence.refresh_lifecycle(trait.trait_id)
    await links.link(TraitMemoryLink(
        trait_id=trait.trait_id, memory_kind="semantic", memory_id=2,
        relation="supports", evidence_ms=1,
    ))
    return SemanticMemoryRetriever(
        _Embedder(), _Store({1: (1.0, 0.0), 2: (0.0, 1.0)}), "m",
        trait_reader=reader, trait_links=links,
    )


async def test_trait_link_breaks_live_retriever_tie(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "live_trait.db")
    await db.initialize()
    baseline = await _retriever(db, with_trait=False)
    before = await baseline.rank_fused(_facts(), "猫", 1_000)
    assert before is not None and before[0].fact_id == 1

    with_trait = await _retriever(db, with_trait=True)
    after = await with_trait.rank_fused(_facts(), "猫", 1_000)
    assert after is not None and after[0].fact_id == 2
