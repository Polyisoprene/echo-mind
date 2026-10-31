#!/usr/bin/env python
"""Embed semantic facts through the configured OpenAI-compatible endpoint (D15)."""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
from pathlib import Path

from echomind.adapters.llm.embedding_client import OpenAiEmbeddingGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_vector_repo import SqliteMemoryVectorStore
from echomind.core.config import load_config_from_json

ROOT = Path(__file__).resolve().parents[1]
BATCH = 32


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config_from_json(ROOT / "data" / "config.json")
    if not cfg.embedding.enabled:
        print("embedding is not configured; set api.embeddingModel/BaseUrl/ApiKey")
        return 2

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT id, subject, fact_text FROM semantic_facts ORDER BY id"
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]
    print(f"facts={len(rows)} model={cfg.embedding.model}")
    if not args.apply:
        print("dry-run: pass --apply to embed and store vectors")
        return 0

    db = SqliteDatabase(args.db)
    await db.initialize()
    store = SqliteMemoryVectorStore(db)
    gateway = OpenAiEmbeddingGateway(cfg.embedding)
    try:
        for start in range(0, len(rows), BATCH):
            batch = rows[start:start + BATCH]
            texts = tuple(f"{row[1]} {row[2]}" for row in batch)
            vectors = await gateway.embed(texts)
            for row, vector in zip(batch, vectors, strict=True):
                await store.upsert(
                    memory_kind="semantic", memory_id=int(row[0]),
                    model=cfg.embedding.model, vector=vector,
                )
            print(f"embedded {min(start + BATCH, len(rows))}/{len(rows)}")
    finally:
        await gateway.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
