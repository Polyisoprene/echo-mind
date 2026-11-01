#!/usr/bin/env python
"""Controlled replay on a temp DB copy; never writes the production database."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import tempfile
import time
from pathlib import Path

from echomind.adapters.storage.trait_memory_repo import SqliteTraitMemoryLinkStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import Percept, TurnOutcome
from echomind.mind.subconscious_probe import SubconsciousChordResult

ROOT = Path(__file__).resolve().parents[1]


def _copy(src: Path, dst: Path) -> None:
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    target = sqlite3.connect(dst)
    source.backup(target)
    target.close()
    source.close()


async def run(src: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "replay.db"
        _copy(src, db_path)
        container = await EchoMindContainer.create(db_path=db_path)
        chat = "group:813506156"
        now = int(time.time() * 1000)
        percept = Percept(
            chat_key=chat, scene="group", message_id="controlled-replay",
            timestamp_ms=now, sender_id="replay-user", sender_name="回放用户",
            text="我刚说了一件值得记住的事实",
        )
        chord = SubconsciousChordResult(
            joy=2, explicit_fact="回放用户说他明天要去杭州出差",
        )
        container.cognitive_facade._chord_cache[percept.message_id] = chord  # noqa: SLF001
        outcome = TurnOutcome(
            session_id="controlled-replay", chat_key=chat, triggers=(percept,),
            sent_texts=("记住啦，明天杭州出差",), tools_used=("feiyu_say",),
        )
        await container.cognitive_facade.on_turn_completed(outcome)
        facts = await container.memory_repo.get_semantic_facts(chat)
        fact = next(item for item in facts if "杭州" in item.fact_text)
        traits = await container.working_store.sync_persona_traits()
        voice = next(item for item in traits if "发语音" in item.trait_text)
        links = await SqliteTraitMemoryLinkStore(container.db).list_links(voice.trait_id)
        supports = [link for link in links if not link.is_context]
        shadows = await SqliteTraitShadowStore(container.db).list_shadow(chat)
        return {
            "temp_db": str(db_path), "trait_id": voice.trait_id,
            "fact_id": fact.fact_id, "fact_source_turn": fact.source_turn_id,
            "support_links": [{"memory_id": link.memory_id, "relation": link.relation}
                              for link in supports],
            "ranker_scores": await SqliteTraitMemoryLinkStore(container.db).ranker_scores(
                (voice.trait_id,)
            ),
            "shadow_trait_ids": list(shadows[0].trait_ids) if shadows else [],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "eval" / "baselines" / "controlled-replay-2026-11-01.json",
    )
    args = parser.parse_args()
    report = asyncio.run(run(args.db))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
