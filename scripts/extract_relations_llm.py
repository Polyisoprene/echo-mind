#!/usr/bin/env python
"""LLM relation extraction for narrative facts (P2).

Only relations explicitly supported by the fact text are accepted; evidence
must be a substring of the source. Results are cached per fact.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.relation_repo import SqliteRelationStore
from echomind.core.config import load_config_from_json
from echomind.domain.relation import MemoryRelation

ROOT = Path(__file__).resolve().parents[1]
PREDICATES = {"works_at", "friend", "sibling", "gave_to", "alias", "owns"}
GENERIC_OBJECTS = {
    "群友", "群主", "管理员", "本群管理员名单", "群员", "普通群员", "本群", "群",
    "大家", "所有人", "成员",
}
PRONOUNS = {"我", "他", "她", "它", "他们", "她们"}
HINTS = {
    "works_at": ("工作", "上班", "就职", "公司"),
    "friend": ("朋友",),
    "gave_to": ("给",),
    "owns": ("主人", "属于", "拥有"),
    "alias": ("叫", "昵称", "外号", "小名", "QQ", "称呼", "群友"),
}
SYSTEM = (
    "你是关系抽取器。只抽取事实文本中明确表达的关系，不推断、不补全。"
    "predicate 只能是：works_at, friend, sibling, gave_to, alias, owns。"
    "subject/object 必须是原文中的明确人名、群名或 QQ 号；不要使用代词。"
    "evidence 必须是原文的连续子串。没有明确关系就返回空数组。"
    '输出 JSON：{"relations":[{"subject":"","predicate":"","object":"",'
    '"confidence":0.0,"evidence":""}]}'
)


def _cache_key(source: str, memory_id: int, subject: str, text: str) -> str:
    return hashlib.sha256(f"{source}\n{memory_id}\n{subject}\n{text}".encode()).hexdigest()


def _parse_content(raw: dict[str, Any]) -> list[dict[str, Any]]:
    choices = raw.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return []
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message", {}) if isinstance(first, dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    if not isinstance(content, str):
        return []
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return []
    relations = data.get("relations", []) if isinstance(data, dict) else []
    return [r for r in relations if isinstance(r, dict)] if isinstance(relations, list) else []


def _valid(item: dict[str, Any], text: str) -> dict[str, Any] | None:
    subject = str(item.get("subject", "")).strip()
    obj = str(item.get("object", "")).strip()
    predicate = str(item.get("predicate", "")).strip()
    evidence = str(item.get("evidence", "")).strip()
    bad = (
        not subject or not obj or predicate not in PREDICATES
        or subject in PRONOUNS or obj in GENERIC_OBJECTS or "名单" in obj
        or (subject.isdigit() and len(subject) < 5)
        or (obj.isdigit() and len(obj) < 5)
    )
    if bad or not evidence or evidence not in text:
        return None
    if subject not in evidence or obj not in evidence:
        return None
    if predicate == "sibling" and not any(
        word in evidence for word in ("哥哥", "弟弟", "姐姐", "妹妹")
    ):
        return None
    if predicate in HINTS and not any(word in evidence for word in HINTS[predicate]):
        return None
    confidence = max(0.0, min(1.0, float(item.get("confidence", 0.7))))
    return {"subject": subject, "predicate": predicate, "object": obj,
            "confidence": confidence, "evidence": evidence}


async def _batch(
    gateway: FailoverLlmGateway, rows: list[tuple[int, str, str]]
) -> list[dict[str, Any]]:
    lines = [f"[{fact_id}] subject={subject}\n{text}" for fact_id, subject, text in rows]
    prompt = "抽取以下事实中的关系：\n\n" + "\n\n".join(lines)
    raw = await gateway.complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=1500, thinking_off=True, json_mode=True,
        chat_key="relation-extract",
    )
    found: list[dict[str, Any]] = []
    for item in _parse_content(raw):
        for fact_id, _subject, text in rows:
            valid = _valid(item, text)
            if valid is not None:
                valid["fact_id"] = fact_id
                found.append(valid)
                break
    return found


def _load_rows(db: Path, limit: int, source: str) -> list[tuple[int, str, str]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    if source == "facts":
        rows = [
            (int(fact_id), str(subject), str(text))
            for fact_id, subject, text in conn.execute(
                "SELECT id, subject, fact_text FROM semantic_facts ORDER BY id"
            )
        ]
    else:
        rows = []
        for memory_id, participants_json, summary, detail in conn.execute(
            "SELECT id, participants_json, summary, key_detail FROM episodic_memories "
            "WHERE sensitivity != 'secret' ORDER BY id"
        ):
            participants = json.loads(str(participants_json or "[]"))
            if not participants:
                continue
            rows.append((int(memory_id), str(participants[0]),
                         f"{summary}；{detail or ''}"))
    return rows[:limit] if limit else rows


def _load_cache(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    data: dict[str, list[dict[str, Any]]] = json.loads(path.read_text(encoding="utf-8"))
    return data


async def _extract_all(
    gateway: FailoverLlmGateway, pending: list[tuple[int, str, str]],
    batch: int, cache: dict[str, list[dict[str, Any]]], cache_path: Path,
    *, source: str,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for start in range(0, len(pending), batch):
        chunk = pending[start:start + batch]
        try:
            chunk_found = await _batch(gateway, chunk)
        except Exception as exc:  # noqa: BLE001 - report and continue batch
            print(f"batch failed at {start}: {exc}")
            continue
        found.extend(chunk_found)
        for fact_id, subject, text in chunk:
            cache[_cache_key(source, fact_id, subject, text)] = [
                item for item in chunk_found if item["fact_id"] == fact_id
            ]
        await asyncio.to_thread(cache_path.write_text,
                                json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"batch {start + len(chunk)}/{len(pending)} relations={len(found)}")
    return found


def _report(rows: list[tuple[int, str, str]], pending: list[tuple[int, str, str]],
            found: list[dict[str, Any]]) -> None:
    counts = Counter(str(item["predicate"]) for item in found)
    print(f"facts={len(rows)} pending={len(pending)} relations={len(found)} "
          f"predicates={dict(counts)}")
    for item in found[:25]:
        print(f"  {item['subject']} --{item['predicate']}--> {item['object']}  "
              f"({item['evidence'][:40]})")


async def _apply(db: SqliteDatabase, found: list[dict[str, Any]]) -> int:
    store = SqliteRelationStore(db)
    for item in found:
        await store.upsert(MemoryRelation(
            subject_id=str(item["subject"]), predicate=str(item["predicate"]),
            object_id=str(item["object"]), source_memory_id=int(item["fact_id"]),
            confidence=float(item["confidence"]),
        ))
    return len(found)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cache", type=Path, default=ROOT / "data" / "relation_llm_cache.json")
    parser.add_argument("--source", choices=("facts", "episodes"), default="facts")
    args = parser.parse_args()

    rows = _load_rows(args.db, args.limit, args.source)
    cache = _load_cache(args.cache)
    pending = [row for row in rows
               if _cache_key(args.source, *row) not in cache]
    found: list[dict[str, Any]] = []
    for fact_id, subject, text in rows:
        for item in cache.get(_cache_key(args.source, fact_id, subject, text), []):
            valid = _valid(item, text)
            if valid is not None:
                valid["fact_id"] = fact_id
                found.append(valid)

    cfg = load_config_from_json(ROOT / "data" / "config.json")
    db = SqliteDatabase(args.db)
    await db.initialize()
    gateway = FailoverLlmGateway(cfg.primary_llm, cfg.fallback_llm, db)
    found.extend(await _extract_all(
        gateway, pending, args.batch, cache, args.cache, source=args.source
    ))
    _report(rows, pending, found)
    if not args.apply:
        print("dry-run: pass --apply to write")
        return 0
    print(f"applied {await _apply(db, found)} relations")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
