#!/usr/bin/env python
"""D15: measure lexical retrieval recall on paraphrase queries (no model calls)."""

from __future__ import annotations

import json
from pathlib import Path

from echomind.domain.models import SemanticFact
from echomind.mind.ebbinghaus import select_relevant_facts

ROOT = Path(__file__).resolve().parents[1]

# (query, target fact text) — paraphrases deliberately avoid the target's wording.
PAIRS: tuple[tuple[str, str], ...] = (
    ("家里那只小东西最近胃口不好", "橘猫的猫粮吃得很少"),
    ("那份工作还顺利吗", "新岗位还在适应"),
    ("你昨晚几点睡的", "熬夜到凌晨两点"),
    ("假期想出门走走吗", "周末计划去爬山"),
    ("她平时喝什么咖啡", "只喝美式"),
    ("材料什么时候要交", "下周三截止"),
    ("L 最近身体怎么样", "在休养"),
    ("那部片子看完哭了吗", "电影很催泪"),
    ("天气不好会害怕吗", "怕打雷"),
    ("这个月钱够花吗", "预算超了"),
)

DISTRACTORS: tuple[tuple[str, str], ...] = (
    ("群规", "周五晚上发图"),
    ("梗", "B 站热门视频"),
    ("游戏", "昨晚排位连胜"),
    ("天气", "今天降温"),
    ("外卖", "中午吃了面"),
    ("宠物", "楼下狗很吵"),
    ("工作", "周报还没写"),
    ("学习", "单词背到第三单元"),
    ("出行", "地铁二号线停运"),
    ("电影", "新片下周上映"),
    ("音乐", "循环一首老歌"),
    ("睡眠", "午睡二十分钟"),
    ("饮食", "少糖少冰"),
    ("运动", "跑步三公里"),
    ("购物", "买了双鞋"),
    ("家务", "周末大扫除"),
    ("朋友", "老同学来出差"),
    ("计划", "下月去海边"),
    ("健康", "体检报告正常"),
    ("心情", "今天有点低落"),
)


def _facts() -> tuple[SemanticFact, ...]:
    rows = [("目标", text) for _q, text in PAIRS]
    rows += list(DISTRACTORS)
    return tuple(
        SemanticFact(chat_key="eval", subject=subject, fact_text=text, confidence=0.9)
        for subject, text in rows
    )


def main() -> int:
    facts = _facts()
    hits = 0
    details: list[dict[str, object]] = []
    for query, target in PAIRS:
        picked = select_relevant_facts(facts, query, limit=5)
        texts = [f.fact_text for f in picked]
        found = target in texts
        hits += int(found)
        details.append({"query": query, "target": target, "found": found,
                        "rank": texts.index(target) + 1 if found else None})
    payload = {"n": len(PAIRS), "recall_at_5": round(hits / len(PAIRS), 3),
               "details": details}
    out = ROOT / "reports" / "memory_retrieval_baseline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"recall@5 = {hits}/{len(PAIRS)} = {payload['recall_at_5']}")
    for row in details:
        print(f"  {'OK ' if row['found'] else 'MISS'} {row['query']}")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
