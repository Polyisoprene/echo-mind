"""The production facade must record active traits and causal links in one turn."""

from __future__ import annotations

from pathlib import Path

from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import PersonaTrait, SemanticFact, TurnOutcome
from echomind.domain.trait_evidence import TraitEvidence


async def test_facade_shadow_and_causal_link(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "facade_trait.db")
    trait_text = "看到群友发图或视频会凑上去仔细看细节，顺着画面里的小槽点接话"
    traits = await container.working_store.sync_persona_traits(
        new_trait=PersonaTrait(category="habit", trait_text=trait_text, strength=6),
        chat_key="group:x", source="turn:t1",
    )
    trait = next(item for item in traits if item.trait_text == trait_text)
    evidence = SqliteTraitEvidenceStore(container.db)
    for index, context in enumerate(("c1", "c2"), 1):
        await evidence.record_trait_evidence(TraitEvidence(
            trait_id=trait.trait_id, session_id=f"s{index}", turn_id=f"t{index}",
            quote="真实行为", quote_kind="assistant", polarity=1,
            context_hash=context, created_ms=index,
        ))
    await evidence.refresh_lifecycle(trait.trait_id)
    fact = SemanticFact(
        chat_key="group:x", subject="图", fact_text="看到图会先找小槽点",
        source_turn_id="turn-facade",
    )
    await container.memory_repo.upsert_semantic_fact(fact)
    facts = await container.memory_repo.get_semantic_facts("group:x")
    target = next(item for item in facts if item.fact_text == fact.fact_text)
    container.cognitive_facade._included["group:x"] = (  # noqa: SLF001
        (target.fact_id, target.subject, target.fact_text),
    )
    outcome = TurnOutcome(
        session_id="turn-facade", chat_key="group:x", triggers=(),
        sent_texts=("图里那个小槽点好明显",), tools_used=("look_at_image",),
        social_reward=0.6,
    )
    await container.cognitive_facade.on_turn_completed(outcome)
    links = await SqliteTraitMemoryLinkStore(container.db).list_links(trait.trait_id)
    supports = [
        link for link in links
        if link.memory_id == target.fact_id and link.relation == "supports"
        and not link.is_context
    ]
    assert len(supports) == 1
    shadows = await SqliteTraitShadowStore(container.db).list_shadow("group:x")
    assert shadows and trait.trait_id in shadows[0].trait_ids


async def test_same_turn_explicit_fact_becomes_support(tmp_path: Path) -> None:
    from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
    from echomind.domain.models import Percept
    from echomind.domain.trait_evidence import TraitEvidence
    from echomind.mind.subconscious_probe import SubconsciousChordResult

    container = await EchoMindContainer.create(db_path=tmp_path / "explicit.db")
    text = "情绪上来或被哄开心时会直接发语音亲口说给对方听"
    traits = await container.working_store.sync_persona_traits(
        new_trait=PersonaTrait(category="habit", trait_text=text, strength=6),
        chat_key="group:x", source="turn:t1",
    )
    trait = next(item for item in traits if item.trait_text == text)
    evidence = SqliteTraitEvidenceStore(container.db)
    for index, context in enumerate(("c1", "c2"), 1):
        await evidence.record_trait_evidence(TraitEvidence(
            trait_id=trait.trait_id, session_id=f"s{index}", turn_id=f"t{index}",
            quote="真实行为", quote_kind="assistant", polarity=1,
            context_hash=context, created_ms=index,
        ))
    await evidence.refresh_lifecycle(trait.trait_id)
    percept = Percept(
        chat_key="group:x", scene="group", message_id="m-explicit",
        timestamp_ms=1, sender_id="u", sender_name="用户", text="陈述事实",
    )
    container.cognitive_facade._chord_cache["m-explicit"] = SubconsciousChordResult(  # noqa: SLF001
        explicit_fact="用户说他明天去杭州",
    )
    outcome = TurnOutcome(
        session_id="turn-explicit", chat_key="group:x", triggers=(percept,),
        sent_texts=("记住啦，明天杭州",), tools_used=("feiyu_say",),
    )
    await container.cognitive_facade.on_turn_completed(outcome)
    facts = await container.memory_repo.get_semantic_facts("group:x")
    fact = next(item for item in facts if "杭州" in item.fact_text)
    links = await SqliteTraitMemoryLinkStore(container.db).list_links(trait.trait_id)
    supports = [
        link for link in links
        if link.memory_id == fact.fact_id and not link.is_context
    ]
    assert len(supports) == 1
    assert fact.source_turn_id == "turn-explicit"
