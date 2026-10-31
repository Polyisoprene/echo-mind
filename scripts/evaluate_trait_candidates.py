#!/usr/bin/env python
"""Evaluate trait candidates structurally; no composite score, no auto-promotion."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from persona_replay import run_stream

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.trait_evidence_repo import SqliteTraitEvidenceStore
from echomind.adapters.storage.trait_shadow_repo import SqliteTraitShadowStore
from echomind.core.config import load_config_from_json
from echomind.mind.trait_generation import TraitTextGenerator

ROOT = Path(__file__).resolve().parents[1]


def _bigrams(text: str) -> set[str]:
    compact = "".join(ch for ch in text if not ch.isspace())
    return {compact[i:i + 2] for i in range(max(0, len(compact) - 1))}


def _jaccard(left: str, right: str) -> float:
    a, b = _bigrams(left), _bigrams(right)
    return round(len(a & b) / max(1, len(a | b)), 3)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=("warm", "offense", "mixed"), default="warm")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="echo-candidate-eval-"))
    db_path = workdir / "replay.db"
    replay = await run_stream(args.stream, args.days, db_path)
    db = SqliteDatabase(db_path)
    await db.initialize()
    active = await SqliteTraitShadowStore(db).active_traits()
    if not active:
        print("no active traits")
        return 0
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    llm = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    generator = TraitTextGenerator(llm, cfg.primary_llm.model)
    evidence_store = SqliteTraitEvidenceStore(db)
    async with db.connect() as conn:
        cursor = await conn.execute("SELECT trait_text FROM persona_traits")
        existing = [str(row[0]) for row in await cursor.fetchall()]

    results = []
    for trait in active:
        evidence = await evidence_store.list_trait_evidence(trait.trait_id, 200)
        source = " ".join(item.quote for item in evidence)
        samples = [
            await generator.generate(trait.trait_id, evidence)
            for _ in range(args.repeats)
        ]
        texts = [
            item.trait_text for item in samples
            if item is not None and item.status == "candidate"
        ]
        stability = [
            _jaccard(texts[i], texts[j])
            for i in range(len(texts)) for j in range(i + 1, len(texts))
        ]
        results.append({
            "trait_id": trait.trait_id,
            "category": trait.category,
            "samples": [
                {"status": None if item is None else item.status,
                 "text": None if item is None else item.trait_text,
                 "reject_reason": None if item is None else item.reject_reason}
                for item in samples
            ],
            "valid_count": len(texts),
            "exact_match_rate": round(
                sum(text == texts[0] for text in texts) / len(texts), 3
            ) if texts else 0.0,
            "mean_pairwise_jaccard": (
                round(sum(stability) / len(stability), 3) if stability else 0.0
            ),
            "evidence_bigram_overlap": _jaccard(texts[0], source) if texts else 0.0,
            "max_template_similarity": max(
                (_jaccard(text, old) for text in texts for old in existing),
                default=0.0,
            ),
        })
    report = {"replay": replay, "repeats": args.repeats, "results": results}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
