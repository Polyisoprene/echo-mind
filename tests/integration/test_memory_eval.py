"""D19: reproducible memory acceptance baseline (authorization, source, consistency)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import PlasticParamSpec, SemanticFact, SocialBondProfile
from echomind.domain.ports import IDisclosureLog
from echomind.mind.facade_memory import gate_frame
from echomind.mind.person_level import PersonProfile
from echomind.mind.persona_stance import apply_stance_for


class _Log:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def log_disclosure(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _params() -> dict[str, PlasticParamSpec]:
    return {
        key: PlasticParamSpec(key=key, value=50.0, min_bound=0.0, max_bound=100.0)
        for key in ("persona_warmth", "persona_tsundere", "persona_playfulness",
                    "persona_defiance", "persona_confidence")
    }


@pytest.mark.asyncio
async def test_memory_acceptance_baseline(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "eval.db")
    repo = container.memory_repo
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="group:1", subject="L 的病", fact_text="最近在休养",
        scope="person", owner_id="L", sensitivity="private"))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="group:1", subject="暗号", fact_text="只告诉过你",
        scope="person", owner_id="L", sensitivity="secret"))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="group:1", subject="群规", fact_text="周五发图",
        scope="venue", sensitivity="group"))
    await repo.upsert_semantic_fact(SemanticFact(
        chat_key="global", subject="公开梗", fact_text="B 站热门",
        scope="global", sensitivity="public"))

    group1 = {f.subject for f in await repo.get_semantic_facts("group:1")}
    group2 = {f.subject for f in await repo.get_semantic_facts("group:2")}
    private_l = {f.subject for f in await repo.get_semantic_facts("private:L")}
    private_m = {f.subject for f in await repo.get_semantic_facts("private:M")}

    assert "L 的病" in group1 and "L 的病" in private_l
    assert "L 的病" not in group2 | private_m
    assert "暗号" not in group1 | group2 | private_l | private_m
    assert "群规" in group1 and "群规" not in group2 | private_l | private_m
    assert "公开梗" in group1 & group2 & private_l & private_m

    all_facts = await repo.get_semantic_facts("group:1")
    assert all(f.source_venue_id for f in all_facts), "every fact keeps its source venue"

    private_fact = next(f for f in all_facts if f.subject == "L 的病")
    log = _Log()
    kept, _ = await gate_frame(
        (private_fact,), (), frozenset({"M"}), "group:1", cast(IDisclosureLog, log))
    assert kept == ()
    assert log.calls[-1]["reason"] == "owner_absent"

    profile = PersonProfile(person_id="L", trust=0.66, affinity=54.0,
                            depth_raw=3.0, depth_percentile=92.0)
    group_bond = SocialBondProfile(chat_key="group:1", user_id="L", user_name="L",
                                   affinity_score=64.0, trust_score=0.66)
    private_bond = SocialBondProfile(chat_key="private:L", user_id="L", user_name="L",
                                     affinity_score=32.0, trust_score=0.66)
    g = apply_stance_for(_params(), {"L": group_bond}, "L", {"L": profile})
    p = apply_stance_for(_params(), {"L": private_bond}, "L", {"L": profile})
    assert abs(g["persona_warmth"].value - p["persona_warmth"].value) < 0.01
    assert abs(g["persona_defiance"].value - p["persona_defiance"].value) < 0.01
    assert g["persona_playfulness"].value > p["persona_playfulness"].value + 2.0
