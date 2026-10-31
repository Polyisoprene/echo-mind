#!/usr/bin/env python
"""Export 30 same-scenario A/B pairs for human pairwise preference."""

from __future__ import annotations

import csv
import html
import itertools
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval" / "calibration" / "persona_v1"
OUT = ROOT / "eval" / "calibration" / "persona_pairwise_v1"
HEADERS = ["编号", "场景编号", "她面对的场面", "期望方向", "回复A", "回复B",
           "哪条更像真人(A/B/平局/都差)", "哪条更适合发群(A/B/平局/都差)", "备注"]


def _load() -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    rows = list(csv.DictReader((BASE / "items.csv").open(encoding="utf-8-sig")))
    key = {item["item_id"]: item for item in json.loads(
        (BASE / "key.json").read_text(encoding="utf-8"))["items"]}
    return rows, key


def _pair_options(
    group: list[dict[str, str]], key: dict[str, dict[str, Any]]
) -> list[tuple[str, str]]:
    ordered = sorted(group, key=lambda r: -int(r["总体(1-5)"]))
    options: list[tuple[str, str]] = []
    for left, right in itertools.combinations(ordered, 2):
        left_model = key[left["编号"]]["model"]
        right_model = key[right["编号"]]["model"]
        if left_model != right_model:
            options.append((left["编号"], right["编号"]))
    if not options:
        options = [(a["编号"], b["编号"]) for a, b in itertools.combinations(ordered, 2)]
    return options


def _take(
    options: list[tuple[str, str]], used: set[frozenset[str]]
) -> tuple[str, str] | None:
    for left, right in options:
        if frozenset((left, right)) not in used:
            return left, right
    return None


def _select(
    groups: dict[str, list[dict[str, str]]], key: dict[str, dict[str, Any]],
    rng: random.Random,
) -> list[tuple[str, str]]:
    options: dict[str, list[tuple[str, str]]] = {}
    for scenario in sorted(groups):
        pairs = _pair_options(groups[scenario], key)
        rng.shuffle(pairs)
        options[scenario] = pairs
    selected: list[tuple[str, str]] = []
    used: set[frozenset[str]] = set()
    for _ in range(3):
        for scenario in sorted(options):
            pair = _take(options[scenario], used)
            if pair is None:
                continue
            selected.append(pair)
            used.add(frozenset(pair))
            if len(selected) >= 30:
                return selected
    return selected


def main() -> int:
    rows, key = _load()
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row["场景编号"], []).append(row)
    rng = random.Random(20261031)  # noqa: S311 - deterministic form sampling
    selected = _select(groups, key, rng)
    rng.shuffle(selected)
    by_id = {row["编号"]: row for row in rows}
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = []
    with (OUT / "pairs.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        for index, (left, right) in enumerate(selected[:30], 1):
            a, b = by_id[left], by_id[right]
            if rng.random() < 0.5:
                a, b = b, a
            writer.writerow({
                "编号": f"Q{index:03d}", "场景编号": a["场景编号"],
                "她面对的场面": a["她面对的场面"], "期望方向": a["期望方向"],
                "回复A": a["她的回复"], "回复B": b["她的回复"],
                "哪条更像真人(A/B/平局/都差)": "",
                "哪条更适合发群(A/B/平局/都差)": "", "备注": "",
            })
            pairs.append({
                "pair_id": f"Q{index:03d}", "scenario": a["场景编号"],
                "a": {"item_id": a["编号"], "model": key[a["编号"]]["model"],
                      "human_overall": int(a["总体(1-5)"])},
                "b": {"item_id": b["编号"], "model": key[b["编号"]]["model"],
                      "human_overall": int(b["总体(1-5)"])},
            })
    (OUT / "key.json").write_text(json.dumps({"pairs": pairs}, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    html_rows = []
    for pair in pairs:
        row = by_id[pair["a"]["item_id"]]
        other = by_id[pair["b"]["item_id"]]
        html_rows.append(
            f"<tr><td>{pair['pair_id']}</td><td>{html.escape(row['她面对的场面'])}</td>"
            f"<td>{html.escape(row['期望方向'])}</td>"
            f"<td>{html.escape(row['她的回复'])}</td><td>{html.escape(other['她的回复'])}</td>"
            "<td></td><td></td><td></td></tr>"
        )
    doc = f"""<!doctype html><meta charset="utf-8"><title>人格成对比较 30 组</title>
<style>body{{font-family:sans-serif;margin:24px}}td,th{{border:1px solid #ccc;padding:6px;
vertical-align:top}}th{{background:#f3f3f3}}table{{border-collapse:collapse;width:100%}}</style>
<h1>人格成对比较：30 组</h1>
<p>同场景两条回复，选“哪条更像真人”“哪条更适合发群”；可填 A / B / 平局 / 都差。</p>
<table><thead><tr><th>编号</th><th>她面对的场面</th><th>期望方向</th><th>回复A</th>
<th>回复B</th><th>更像真人</th><th>更适合发群</th><th>备注</th></tr></thead>
<tbody>{''.join(html_rows)}</tbody></table>"""
    (OUT / "pairs.html").write_text(doc, encoding="utf-8")
    print("pairs", len(pairs), "out", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
