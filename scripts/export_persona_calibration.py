#!/usr/bin/env python
"""Export 50 human-calibration items with clear Chinese headers."""

from __future__ import annotations

import csv
import html
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "eval" / "datasets" / "persona_judge_v1" / "scenarios.json"
OUT = ROOT / "eval" / "calibration" / "persona_v1"
DIMENSIONS = ("人格一致性(1-5)", "自然度(1-5)", "边界感(1-5)", "总体(1-5)")


def _scenarios() -> dict[str, dict[str, str]]:
    data = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    return {str(item["id"]): item for item in data["scenarios"]}


def _pool() -> dict[str, list[dict[str, Any]]]:
    pool: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((ROOT / "reports").glob("pj_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        model = str(data.get("model", "?"))
        for row in data.get("rows", []):
            scores = row.get("scores", {})
            if not isinstance(scores, dict) or float(scores.get("overall", 0)) <= 0:
                continue
            reply = str(row.get("reply", "")).strip()
            if not reply:
                continue
            pool.setdefault(str(row.get("id")), []).append({
                "model": model, "reply": reply, "scores": scores,
            })
    return pool


def _dedupe(items: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        reply = str(item["reply"])
        if reply not in seen:
            seen.add(reply)
            unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def _pick(pool: dict[str, list[dict[str, Any]]], scenario_ids: list[str]) -> list[dict[str, Any]]:
    rng = random.Random(20261031)  # noqa: S311 - deterministic human-form sampling
    picked: list[dict[str, Any]] = []
    for sid in scenario_ids:
        variants = pool.get(sid, [])
        rng.shuffle(variants)
        picked.extend({**item, "scenario": sid} for item in variants[:4])
    extras = [{**item, "scenario": sid}
              for sid in scenario_ids for item in pool.get(sid, [])[4:5]]
    rng.shuffle(extras)
    picked.extend(extras)
    unique = _dedupe(picked)
    if len(unique) < 50:
        all_items = [{**item, "scenario": sid}
                     for sid in scenario_ids for item in pool.get(sid, [])]
        rng.shuffle(all_items)
        unique = _dedupe(unique + all_items)
    return unique[:50]


def main() -> int:
    scenario = _scenarios()
    pool = _pool()
    items = _pick(pool, sorted(scenario))
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "items.csv"
    headers = ["编号", "场景编号", "她面对的场面", "期望方向", "她的回复", *DIMENSIONS, "备注"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for index, item in enumerate(items, 1):
            sid = str(item["scenario"])
            writer.writerow({
                "编号": f"P{index:03d}", "场景编号": sid,
                "她面对的场面": scenario[sid]["user"],
                "期望方向": scenario[sid]["expect"],
                "她的回复": " ".join(str(item["reply"]).split()),
                **dict.fromkeys(DIMENSIONS, ""), "备注": "",
            })
    key = {"items": [{
        "item_id": f"P{index:03d}", "scenario": str(item["scenario"]),
        "model": item["model"], "judge_scores": item["scores"],
    } for index, item in enumerate(items, 1)]}
    (OUT / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for index, item in enumerate(items, 1):
        sid = str(item["scenario"])
        cells = (f"<td>{html.escape(str(item['reply']))}</td>"
                 "<td></td><td></td><td></td><td></td>")
        rows.append(
            f"<tr><td>P{index:03d}</td><td>{html.escape(scenario[sid]['user'])}</td>"
            f"<td>{html.escape(scenario[sid]['expect'])}</td>{cells}</tr>"
        )
    html_doc = f"""<!doctype html><meta charset="utf-8"><title>人格校准 50 条</title>
<style>body{{font-family:sans-serif;margin:24px}}
td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}
th{{background:#f3f3f3}}table{{border-collapse:collapse;width:100%}}</style>
<h1>人格校准：50 条中文评分表</h1>
<p>先看“她面对的场面”和“期望方向”，再看“她的回复”。
每项填 1–5 的整数；打分标准见 <b>评分说明.md</b>。</p>
<table><thead><tr><th>编号</th><th>她面对的场面</th><th>期望方向</th><th>她的回复</th>
<th>人格一致性</th><th>自然度</th><th>边界感</th><th>总体</th><th>备注</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""
    (OUT / "items.html").write_text(html_doc, encoding="utf-8")
    print(f"items={len(items)} csv={csv_path} html={OUT / 'items.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
