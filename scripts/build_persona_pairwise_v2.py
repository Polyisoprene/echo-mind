#!/usr/bin/env python
"""Generate 60 new A/B pairs from the v2 scenario set."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import html
import json
import random
import sqlite3
from pathlib import Path
from typing import Any

from echomind.adapters.llm.client import FailoverLlmGateway
from echomind.adapters.storage.database import SqliteDatabase
from echomind.core.config import load_config_from_json
from echomind.domain.models import PersonaTrait, PlasticParamSpec
from echomind.domain.persona_specs import PERSONA_SPECS, persona_default
from echomind.mind.personality import synthesize_live_persona_directive

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "eval" / "datasets" / "persona_judge_v2" / "scenarios.json"
OUT = ROOT / "eval" / "calibration" / "persona_pairwise_v2"
MODELS = ("deepseek-v4.1-flash", "kimi-k3", "glm-5.3",
          "minimax-m3.1-flash", "mimo-v2.6-pro", "deepseek-v4-pro")
HEADERS = ["编号", "场景编号", "她面对的场面", "回复A", "回复B",
           "哪条更像真人(A/B/平局/都差)", "哪条更适合发群(A/B/平局/都差)", "备注"]


def _params(db: Path) -> dict[str, PlasticParamSpec]:
    values = {key: persona_default(key) for key in PERSONA_SPECS}
    if db.exists():
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for key, value in conn.execute("SELECT key, value FROM plastic_params"):
            if key in values:
                values[key] = float(value)
    return {key: PlasticParamSpec(key=key, value=value, min_bound=0.0, max_bound=100.0)
            for key, value in values.items()}


def _traits(db: Path) -> tuple[PersonaTrait, ...]:
    if not db.exists():
        return ()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    return tuple(PersonaTrait(category=str(cat), trait_text=str(text),
                              strength=int(strength), evidence_count=int(evidence))
                 for cat, text, strength, evidence in conn.execute(
                     "SELECT category, trait_text, strength, evidence_count FROM persona_traits"))


def _content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message", {}) if isinstance(first, dict) else {}
    return str(message.get("content", "")).strip() if isinstance(message, dict) else ""


async def _reply(gateway: FailoverLlmGateway, system: str, user: str, model: str) -> str:
    raw = await gateway.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.7, max_tokens=220, thinking_off=True,
        chat_key="pairwise-v2", model_override=model,
    )
    return _content(raw)


async def _generate(gateway: FailoverLlmGateway, system: str, scenario: dict[str, str],
                    cache: dict[str, str], cache_path: Path) -> tuple[str, str] | None:
    for model in (MODELS[int(scenario["id"][3:]) % 6],
                  MODELS[(int(scenario["id"][3:]) + 2) % 6]):
        key = hashlib.sha256(f"{scenario['id']}\n{model}".encode()).hexdigest()
        if key not in cache:
            try:
                reply = await _reply(gateway, system, str(scenario["user"]), model)
            except Exception as exc:  # noqa: BLE001
                print(f"{scenario['id']} {model} failed: {exc}")
                continue
            if not reply:
                continue
            cache[key] = reply
            await asyncio.to_thread(
                cache_path.write_text, json.dumps(cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return model, cache[key]
        return model, cache[key]
    return None


async def _build_pair(
    gateway: FailoverLlmGateway, system: str, scenario: dict[str, str],
    cache: dict[str, str], cache_path: Path,
) -> dict[str, Any] | None:
    generated = await _generate(gateway, system, scenario, cache, cache_path)
    if generated is None:
        return None
    model_a, reply_a = generated
    model_b = MODELS[(MODELS.index(model_a) + 1) % len(MODELS)]
    key_b = hashlib.sha256(f"{scenario['id']}\n{model_b}-b".encode()).hexdigest()
    if key_b not in cache:
        try:
            cache[key_b] = await _reply(gateway, system, str(scenario["user"]), model_b)
        except Exception as exc:  # noqa: BLE001
            print(f"{scenario['id']} {model_b} failed: {exc}")
            return None
        if not cache[key_b]:
            return None
        await asyncio.to_thread(
            cache_path.write_text, json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {"id": scenario["id"], "user": scenario["user"],
            "a": {"model": model_a, "reply": reply_a},
            "b": {"model": model_b, "reply": cache[key_b]}}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--cache", type=Path, default=ROOT / "data" / "pairwise_v2_cache.json")
    args = parser.parse_args()

    data = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    scenarios = data["scenarios"][:args.limit] if args.limit else data["scenarios"]
    cfg = load_config_from_json(ROOT / "data" / "config.json")
    persona = synthesize_live_persona_directive(_params(ROOT / "data" / "echomind.db"),
                                                _traits(ROOT / "data" / "echomind.db"))
    system = f"你是「{cfg.bot_name}」。{cfg.role_text}\n{persona}\n只回复群聊内容，不解释规则。"
    cache: dict[str, str] = {}
    if args.cache.exists():
        cache = json.loads(args.cache.read_text(encoding="utf-8"))
    db = SqliteDatabase(ROOT / "data" / "echomind.db")
    await db.initialize()
    gateway = FailoverLlmGateway(cfg.primary_llm, cfg.fallback_llm, db)

    pairs: list[dict[str, Any]] = []
    for scenario in scenarios:
        pair = await _build_pair(gateway, system, scenario, cache, args.cache)
        if pair is not None:
            pairs.append(pair)

    rng = random.Random(20261101)  # noqa: S311 - deterministic form sampling
    OUT.mkdir(parents=True, exist_ok=True)
    key_rows = []
    html_rows = []
    with (OUT / "pairs.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        for index, pair in enumerate(pairs, 1):
            a, b = pair["a"], pair["b"]
            if rng.random() < 0.5:
                a, b = b, a
            writer.writerow({
                "编号": f"R{index:03d}", "场景编号": pair["id"],
                "她面对的场面": pair["user"], "回复A": a["reply"], "回复B": b["reply"],
                "哪条更像真人(A/B/平局/都差)": "",
                "哪条更适合发群(A/B/平局/都差)": "", "备注": "",
            })
            key_rows.append({"pair_id": f"R{index:03d}", "scenario": pair["id"],
                             "a": {"model": a["model"], "reply": a["reply"]},
                             "b": {"model": b["model"], "reply": b["reply"]}})
            html_rows.append(
                f"<tr><td>R{index:03d}</td><td>{html.escape(pair['user'])}</td>"
                f"<td>{html.escape(a['reply'])}</td><td>{html.escape(b['reply'])}</td>"
                "<td></td><td></td><td></td></tr>")
    (OUT / "key.json").write_text(json.dumps({"pairs": key_rows}, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    doc = f"""<!doctype html><meta charset="utf-8"><title>人格成对比较 v2（60 组）</title>
<style>body{{font-family:sans-serif;margin:24px}}td,th{{border:1px solid #ccc;padding:6px;
vertical-align:top}}th{{background:#f3f3f3}}table{{border-collapse:collapse;width:100%}}</style>
<h1>人格成对比较 v2：60 组新场景</h1>
<p>同场景两条回复，选“哪条更像真人”“哪条更适合发群”；可填 A / B / 平局 / 都差。</p>
<table><thead><tr><th>编号</th><th>她面对的场面</th><th>回复A</th><th>回复B</th>
<th>更像真人</th><th>更适合发群</th><th>备注</th></tr></thead>
<tbody>{''.join(html_rows)}</tbody></table>"""
    (OUT / "pairs.html").write_text(doc, encoding="utf-8")
    print("pairs", len(pairs), "out", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
