#!/usr/bin/env python
"""Pairwise persona comparison across models with multiple judges."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import load_config_from_json

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("kimi-k3", "glm-5.3", "deepseek-v4.1-flash")
JUDGES = ("glm-5.3", "kimi-k3", "deepseek-v4-pro")
SYSTEM = (
    "你是严格的人格评审。比较两条回复哪条更符合：温柔/傲娇/俏皮/占有/自信/狡黠/叛逆的 7 维人设、"
    "群聊自然度、隐私与越界边界。只输出 JSON：{\"winner\":\"A\"|\"B\"|\"tie\",\"reason\":\"\"}"
)


def _content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message", {}) if isinstance(first, dict) else {}
    return str(message.get("content", "")) if isinstance(message, dict) else ""


def _winner(raw: dict[str, Any]) -> str:
    text = _content(raw)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return ""
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return ""
    value = str(data.get("winner", "")).lower() if isinstance(data, dict) else ""
    return value if value in {"a", "b", "tie"} else ""


def _key(pair: tuple[str, str], scenario: str, judge: str, order: tuple[str, str]) -> str:
    return hashlib.sha256(
        f"{pair}\n{scenario}\n{judge}\n{','.join(order)}".encode()
    ).hexdigest()


def _load() -> tuple[dict[str, dict[str, str]], list[str]]:
    replies: dict[str, dict[str, str]] = {}
    for model in MODELS:
        path = ROOT / "reports" / f"pj_panel_{model}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        replies[model] = {str(row["id"]): str(row["reply"]) for row in data["rows"]}
    ids = sorted(set.intersection(*(set(v) for v in replies.values())))
    return replies, ids


async def _judge_one(
    gateway: FailoverLlmGateway, pair: tuple[str, str], scenario: str, judge: str,
    *, replies: dict[str, dict[str, str]], cache: dict[str, str], cache_path: Path,
) -> str:
    left, right = pair
    digest = hashlib.sha256(f"{pair}{scenario}{judge}".encode()).hexdigest()
    order = (right, left) if int(digest[:2], 16) % 2 == 1 else (left, right)
    key = _key(pair, scenario, judge, order)
    winner = cache.get(key, "")
    if not winner:
        user = (
            f"场景：{scenario}\n回复A：{replies[order[0]][scenario]}\n"
            f"回复B：{replies[order[1]][scenario]}"
        )
        raw = await gateway.complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            temperature=0.0, max_tokens=400, thinking_off=True, json_mode=True,
            chat_key="persona-pairwise", model_override=judge,
        )
        winner = _winner(raw)
        if not winner:
            return ""
        cache[key] = winner
        await asyncio.to_thread(
            cache_path.write_text, json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {"a": order[0], "b": order[1], "tie": "tie"}[winner]


async def _compare(
    gateway: FailoverLlmGateway, pair: tuple[str, str], ids: list[str],
    *, replies: dict[str, dict[str, str]], cache: dict[str, str], cache_path: Path,
) -> tuple[float, int]:
    wins, n = 0.0, 0
    for scenario in ids:
        for judge in JUDGES:
            mapped = await _judge_one(
                gateway, pair, scenario, judge, replies=replies, cache=cache,
                cache_path=cache_path
            )
            if not mapped:
                continue
            n += 1
            if mapped == "tie":
                wins += 0.5
            elif mapped == pair[0]:
                wins += 1.0
    return wins, n


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "pj_pairwise.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "data" / "pj_pairwise_cache.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    replies, ids = _load()
    if args.limit:
        ids = ids[:args.limit]
    cache: dict[str, str] = {}
    if args.cache.exists():
        cache = json.loads(args.cache.read_text(encoding="utf-8"))
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    db = SqliteDatabase(ROOT / "data" / "echomind.db")
    await db.initialize()
    gateway = FailoverLlmGateway(cfg.primary_llm, cfg.fallback_llm, db)

    scores: dict[tuple[str, str], tuple[float, int]] = {}
    for pair in itertools.combinations(MODELS, 2):
        scores[pair] = await _compare(gateway, pair, ids, replies=replies, cache=cache,
                       cache_path=args.cache)

    print("| pair | left win rate | n |")
    print("|---|---:|---:|")
    for pair, (wins, n) in scores.items():
        print(f"| {pair[0]} vs {pair[1]} | {wins / max(1, n):.3f} | {n} |")
    report = {
        "models": MODELS, "judges": JUDGES,
        "pairs": {
            f"{a} vs {b}": {"wins": wins, "n": n, "win_rate": round(wins / max(1, n), 3)}
            for (a, b), (wins, n) in scores.items()
        },
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
